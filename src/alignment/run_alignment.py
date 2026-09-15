"""
Stage 2 entry point.

Usage:
    python -m src.alignment.run_alignment
    python -m src.alignment.run_alignment --boundary data/raw/city_boundary.geojson --resolution 100

Reads Stage 1's interim outputs, reprojects SatPM and WorldPop onto one
common analysis grid in a local UTM CRS, clips both to the city boundary,
samples both rasters at every CPCB station location, aggregates OpenAQ to
monthly means, and joins everything into one station-month feature table --
the direct input to Stage 3.

Writes:
    data/processed/satpm_aligned.tif        (multi-band, one band per month)
    data/processed/satpm_aligned_months.txt (band -> month lookup)
    data/processed/worldpop_aligned.tif
    data/processed/aligned_station_months.parquet
    reports/alignment_summary.md
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import xarray as xr

from . import boundary as boundary_mod
from . import clip, config, crs_utils, grid, station_join, temporal


def run(boundary_path: Path = None, interim_dir: Path = None, processed_dir: Path = None,
        reports_dir: Path = None, resolution_m: float = None):
    boundary_path = Path(boundary_path or config.BOUNDARY_PATH)
    interim_dir = Path(interim_dir or config.INTERIM_DATA_DIR)
    processed_dir = Path(processed_dir or config.PROCESSED_DATA_DIR)
    reports_dir = Path(reports_dir or (config.PROJECT_ROOT / "reports"))
    resolution_m = resolution_m or config.ANALYSIS_RESOLUTION_M
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    summary_lines = ["# Stage 2 -- Alignment Summary\n"]

    # --- 1. Boundary + common grid -----------------------------------------
    city_boundary = boundary_mod.load_boundary(boundary_path)
    bbox = boundary_mod.bbox_of(city_boundary)
    target_crs = crs_utils.utm_crs_for_bbox(**bbox)
    transform, width, height = grid.build_common_grid(bbox, target_crs, resolution_m)
    print(f"Common grid: {width}x{height} px @ {resolution_m}m in {target_crs}")
    summary_lines.append(f"- Target CRS: `{target_crs}` (auto-selected UTM zone)")
    summary_lines.append(f"- Common grid: {width} x {height} px @ {resolution_m} m")

    # --- 2. SatPM: reproject each month onto the common grid, then clip ----
    satpm_ds = xr.open_dataset(interim_dir / "satpm_validated.nc")
    satpm_ds = satpm_ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    if satpm_ds.rio.crs is None:
        satpm_ds = satpm_ds.rio.write_crs(config.STORAGE_CRS)
    src_crs = satpm_ds.rio.crs.to_string()
    src_transform = satpm_ds.rio.transform()

    times = pd.to_datetime(satpm_ds["time"].values)
    aligned_bands = []
    clipped_transform = None
    for t_idx in range(len(times)):
        band = satpm_ds["pm25"].isel(time=t_idx).values.astype("float32")
        resampled, _ = grid.resample_concentration(band, src_transform, src_crs, transform, (height, width), target_crs)
        cropped, cropped_transform = clip.clip_to_boundary(resampled, transform, target_crs, city_boundary)
        aligned_bands.append(cropped)
        clipped_transform = cropped_transform  # same for every band, same grid

    satpm_stack = np.stack(aligned_bands, axis=0)  # (time, H, W)
    with rasterio.open(
        processed_dir / "satpm_aligned.tif", "w", driver="GTiff",
        height=satpm_stack.shape[1], width=satpm_stack.shape[2], count=satpm_stack.shape[0],
        dtype="float32", crs=target_crs, transform=clipped_transform, nodata=np.nan,
    ) as dst:
        for i in range(satpm_stack.shape[0]):
            dst.write(satpm_stack[i], i + 1)
    (processed_dir / "satpm_aligned_months.txt").write_text(
        "\n".join(f"{i+1}\t{pd.Timestamp(t).strftime('%Y-%m')}" for i, t in enumerate(times))
    )
    print(f"SatPM aligned: {satpm_stack.shape}, {len(times)} months, clipped to boundary")
    summary_lines.append(f"- SatPM aligned grid: {satpm_stack.shape} (time, H, W)")

    # --- 3. WorldPop: reproject (mass-preserving) onto the common grid, clip
    with rasterio.open(interim_dir / "worldpop_validated.tif") as src:
        wp_array = src.read(1).astype("float32")
        wp_transform = src.transform
        wp_crs = src.crs.to_string()

    wp_resampled, _ = grid.resample_population_preserving_total(
        wp_array, wp_transform, wp_crs, transform, (height, width), target_crs
    )
    wp_cropped, wp_cropped_transform = clip.clip_to_boundary(wp_resampled, transform, target_crs, city_boundary)

    with rasterio.open(
        processed_dir / "worldpop_aligned.tif", "w", driver="GTiff",
        height=wp_cropped.shape[0], width=wp_cropped.shape[1], count=1,
        dtype="float32", crs=target_crs, transform=wp_cropped_transform, nodata=np.nan,
    ) as dst:
        dst.write(wp_cropped, 1)

    pop_before = float(np.nansum(wp_array))
    pop_after = float(np.nansum(wp_cropped))
    print(f"WorldPop aligned: {wp_cropped.shape}, population before/after clip: "
          f"{pop_before:,.0f} -> {pop_after:,.0f}")
    summary_lines.append(f"- WorldPop aligned grid: {wp_cropped.shape}")
    summary_lines.append(f"- Population sum before clip: {pop_before:,.0f}; after clip (city extent only): {pop_after:,.0f}")

    # --- 4. Station-pixel join ---------------------------------------------
    stations = pd.read_parquet(interim_dir / "cpcb_stations_validated.parquet")
    stations_clean = stations.loc[~stations["_flag_missing_coords"]].copy()
    if "_flag_duplicate_station" in stations_clean.columns:
        n_dupe = int(stations_clean["_flag_duplicate_station"].sum())
        if n_dupe:
            print(f"Dropping {n_dupe} duplicate station_id row(s) flagged in Stage 1 before joining.")
        stations_clean = stations_clean.loc[~stations_clean["_flag_duplicate_station"]]

    stations_clean["population_at_station"] = station_join.sample_raster_at_points(
        wp_cropped, wp_cropped_transform, target_crs, stations_clean
    )
    satpm_samples = station_join.sample_raster_stack_at_points(
        satpm_stack, times, clipped_transform, target_crs, stations_clean
    )

    n_outside = stations_clean["population_at_station"].isna().sum()
    print(f"Stations sampled: {len(stations_clean)} total, {n_outside} fall outside the clipped city grid")
    summary_lines.append(f"- CPCB stations with usable coordinates: {len(stations_clean)}")
    summary_lines.append(f"- Of those, outside the clipped city extent (no pixel match): {n_outside}")

    # --- 5. Temporal alignment of OpenAQ ------------------------------------
    openaq = pd.read_parquet(interim_dir / "openaq_validated.parquet")
    openaq_monthly = temporal.aggregate_openaq_monthly(openaq)
    n_reliable = int(openaq_monthly["reliable"].sum())
    print(f"OpenAQ aggregated to {len(openaq_monthly)} station-months, {n_reliable} meet the completeness threshold")
    summary_lines.append(f"- OpenAQ station-months: {len(openaq_monthly)} ({n_reliable} reliable, "
                          f"completeness >= {config.MIN_MONTHLY_COMPLETENESS:.0%})")

    # --- 6. Join it all into one station-month table ------------------------
    station_meta_cols = [c for c in ["station_id", "station_name", "city", "state",
                                      "latitude", "longitude", "station_type",
                                      "population_at_station"] if c in stations_clean.columns]
    merged = satpm_samples.merge(
        stations_clean[station_meta_cols], on="station_id", how="left"
    )
    merged = merged.merge(
        openaq_monthly.rename(columns={"location_id": "station_id", "mean_pm25": "ground_pm25"}),
        on=["station_id", "month"], how="left", suffixes=("", "_openaq"),
    )

    out_path = processed_dir / "aligned_station_months.parquet"
    merged.to_parquet(out_path, index=False)
    print(f"Aligned station-month table: {len(merged)} rows -> {out_path}")
    summary_lines.append(f"- Final aligned station-month table: {len(merged)} rows -> `{out_path.name}`")

    n_with_ground_truth = merged["ground_pm25"].notna().sum()
    summary_lines.append(f"- Rows with a matched ground-truth reading: {n_with_ground_truth} / {len(merged)}")
    if n_with_ground_truth < len(merged) * 0.5:
        summary_lines.append(
            "  **Warning:** fewer than half the rows matched a ground reading -- check that CPCB "
            "`station_id` and OpenAQ `location_id` actually refer to the same identifiers in the "
            "real data; they may need fuzzy/coordinate-based matching instead of an exact-ID join."
        )

    (reports_dir / "alignment_summary.md").write_text("\n".join(summary_lines) + "\n")
    print(f"\nAlignment summary written to {reports_dir / 'alignment_summary.md'}")

    return merged


def main():
    parser = argparse.ArgumentParser(description="Stage 2: spatial & temporal alignment")
    parser.add_argument("--boundary", type=Path, default=config.BOUNDARY_PATH)
    parser.add_argument("--interim-dir", type=Path, default=config.INTERIM_DATA_DIR)
    parser.add_argument("--processed-dir", type=Path, default=config.PROCESSED_DATA_DIR)
    parser.add_argument("--reports-dir", type=Path, default=config.PROJECT_ROOT / "reports")
    parser.add_argument("--resolution", type=float, default=config.ANALYSIS_RESOLUTION_M)
    args = parser.parse_args()

    try:
        run(
            boundary_path=args.boundary, interim_dir=args.interim_dir,
            processed_dir=args.processed_dir, reports_dir=args.reports_dir,
            resolution_m=args.resolution,
        )
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

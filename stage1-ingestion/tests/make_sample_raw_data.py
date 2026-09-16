"""
Generates small synthetic versions of all four raw sources so Stage 1 can be
run and sanity-checked before the real project data package arrives. Also
deliberately injects a few bad records (missing coords, out-of-range PM2.5,
a duplicate station, an out-of-bbox point) so the validators have something
to actually flag -- a clean run with zero flags would be a weak test.

Usage:
    python tests/make_sample_raw_data.py [--out-dir data/raw]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# Roughly Delhi NCR bounding box, used just to generate plausible coordinates
LAT_RANGE = (28.40, 28.80)
LON_RANGE = (76.85, 77.35)

RNG = np.random.default_rng(42)


def make_cpcb_stations(out_path: Path, n_stations: int = 12):
    lats = RNG.uniform(*LAT_RANGE, n_stations)
    lons = RNG.uniform(*LON_RANGE, n_stations)

    rows = []
    for i in range(n_stations):
        rows.append({
            "Station Code": f"DL{i+1:03d}",
            "Station Name": f"Sample Station {i+1}",
            "City": "Delhi",
            "State": "Delhi",
            "Latitude": lats[i],
            "Longitude": lons[i],
            "Station Type": RNG.choice(["Industrial", "Residential", "Traffic"]),
        })

    # Inject problems: one missing coordinate, one duplicate station code,
    # one point far outside India's bbox.
    rows[2]["Latitude"] = None
    rows.append({**rows[0], "Station Name": "Duplicate of Station 1"})  # duplicate station_id
    rows[5]["Latitude"], rows[5]["Longitude"] = 55.0, 10.0  # nonsense coords (out of bbox)

    df = pd.DataFrame(rows)
    df.to_excel(out_path, index=False, engine="openpyxl")
    print(f"Wrote {len(df)} synthetic CPCB stations -> {out_path}")
    return df


def make_openaq(out_path: Path, station_df: pd.DataFrame, n_months: int = 2):
    records = []
    dates = pd.date_range("2024-01-01", periods=n_months * 28, freq="D")

    for _, station in station_df.iterrows():
        if pd.isna(station["Latitude"]):
            continue
        base_level = RNG.uniform(60, 180)  # plausible Delhi-ish PM2.5 baseline
        for d in dates:
            # simulate ~15% missing days (sensor downtime) at random
            if RNG.random() < 0.15:
                continue
            value = max(0, RNG.normal(base_level, 25))
            records.append({
                "location_id": station["Station Code"],
                "city": station["City"],
                "latitude": station["Latitude"],
                "longitude": station["Longitude"],
                "parameter": "pm25",
                "value": round(value, 1),
                "unit": "ug/m3",
                "date": d.isoformat(),
            })

    df = pd.DataFrame(records)
    # Inject a few bad values
    bad_idx = df.sample(5, random_state=1).index
    df.loc[bad_idx[:2], "value"] = -5           # negative, physically impossible
    df.loc[bad_idx[2:4], "value"] = 5000        # absurdly high
    df.loc[bad_idx[4], "latitude"] = None       # missing coordinate

    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} synthetic OpenAQ records -> {out_path}")
    return df


def make_satpm(out_path: Path, n_months: int = 2, grid_size: int = 20):
    import xarray as xr

    lats = np.linspace(*LAT_RANGE, grid_size)
    lons = np.linspace(*LON_RANGE, grid_size)
    times = pd.date_range("2024-01-01", periods=n_months, freq="MS")

    base = RNG.uniform(70, 150, size=(n_months, grid_size, grid_size))
    base[0, 0, 0] = 1500  # inject one out-of-range cell

    ds = xr.Dataset(
        {"pm25": (("time", "lat", "lon"), base)},
        coords={"time": times, "lat": lats, "lon": lons},
    )
    ds.to_netcdf(out_path)
    print(f"Wrote synthetic SatPM grid {base.shape} -> {out_path}")
    return ds


def make_worldpop(out_path: Path, grid_size: int = 200):
    import rasterio
    from rasterio.transform import from_bounds

    pop = RNG.gamma(shape=2.0, scale=15.0, size=(grid_size, grid_size)).astype("float32")
    pop[0, 0] = -10  # inject an invalid negative cell

    transform = from_bounds(*LON_RANGE, *LAT_RANGE, grid_size, grid_size)
    with rasterio.open(
        out_path, "w", driver="GTiff", height=grid_size, width=grid_size,
        count=1, dtype="float32", crs="EPSG:4326", transform=transform, nodata=-9999,
    ) as dst:
        dst.write(pop, 1)
    print(f"Wrote synthetic WorldPop grid {pop.shape} -> {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    stations = make_cpcb_stations(args.out_dir / "cpcb_caaqms_stations.xlsx")
    make_openaq(args.out_dir / "openaq_historical_archive.csv", stations)
    make_satpm(args.out_dir / "satpm_v6_pm25.nc")
    make_worldpop(args.out_dir / "worldpop_india_100m.tif")


if __name__ == "__main__":
    main()

"""
Stage 3 entry point.

Usage:
    python -m src.features.run_features
    python -m src.features.run_features --center-lat 25.594 --center-lon 85.137

Reads Stage 2's aligned_station_months.parquet, filters to usable rows,
engineers features, assigns spatial CV folds, and writes:
    data/processed/training_table.parquet
    reports/training_table_summary.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import config, engineer, spatial_cv


def run(aligned_path: Path = None, out_dir: Path = None, reports_dir: Path = None,
        met_path: Path = None, center_lat: float = None, center_lon: float = None):
    aligned_path = Path(aligned_path or config.ALIGNED_STATION_MONTHS_PATH)
    out_dir = Path(out_dir or config.PROCESSED_DATA_DIR)
    reports_dir = Path(reports_dir or config.REPORTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(aligned_path)
    funnel = [("aligned station-months (Stage 2 output)", len(df))]

    # --- Filtering funnel ---------------------------------------------
    if config.REQUIRE_RELIABLE_COMPLETENESS and "reliable" in df.columns:
        df = df.loc[df["reliable"] == True]  # noqa: E712 -- explicit, since NaN/None must also drop
        funnel.append(("after requiring reliable monthly completeness", len(df)))

    if config.DROP_IF_MISSING_SATELLITE:
        df = df.loc[df["satellite_pm25"].notna()]
        funnel.append(("after dropping missing satellite_pm25", len(df)))

    if config.DROP_IF_MISSING_GROUND_TRUTH:
        df = df.loc[df[config.TARGET_COLUMN].notna()]
        funnel.append(("after dropping missing ground_pm25", len(df)))

    if df.empty:
        raise ValueError(
            "No rows survive filtering -- check the funnel counts above and Stage 2's output "
            "(reports/alignment_summary.md) before re-running."
        )

    # --- Feature engineering -------------------------------------------
    df = engineer.add_month_cyclical(df)
    df = engineer.add_distance_to_city_center(df, center_lat=center_lat, center_lon=center_lon)
    df = engineer.merge_meteorology(df, met_path or config.METEOROLOGY_PATH)
    df = engineer.impute_missing_covariates(df, config.NUMERIC_FEATURES, config.CATEGORICAL_FEATURES)

    # --- Spatial CV folds -------------------------------------------------
    df = df.reset_index(drop=True)
    fold, strategy = spatial_cv.assign_spatial_folds(df)
    df["cv_fold"] = fold

    # --- Encode categoricals, assemble the final feature matrix -----------
    df_encoded = engineer.one_hot_encode(df, config.CATEGORICAL_FEATURES)

    feature_cols = [c for c in config.NUMERIC_FEATURES if c in df_encoded.columns]
    feature_cols += [
        c for c in df_encoded.columns
        if any(c.startswith(f"{cat}_") for cat in config.CATEGORICAL_FEATURES)
    ]

    keep_cols = (
        ["station_id", "month", "latitude", "longitude", config.TARGET_COLUMN, "cv_fold"]
        + feature_cols
    )
    keep_cols = [c for c in dict.fromkeys(keep_cols) if c in df_encoded.columns]  # dedupe, keep order
    training_table = df_encoded[keep_cols].copy()
    training_table["month"] = training_table["month"].astype(str)  # Period isn't Parquet-native

    out_path = out_dir / "training_table.parquet"
    training_table.to_parquet(out_path, index=False)

    # --- Report -------------------------------------------------------
    fold_report = spatial_cv.fold_summary(training_table)
    target_stats = training_table[config.TARGET_COLUMN].describe()
    n_stations_final = training_table["station_id"].nunique()

    lines = ["# Stage 3 -- Training Table Summary\n", "## Filtering funnel\n",
             "| Step | Rows remaining |", "|---|---:|"]
    for step, n in funnel:
        lines.append(f"| {step} | {n:,} |")
    lines.append("")

    lines.append(f"## Spatial cross-validation\n\nStrategy used: **{strategy}**\n")
    lines.append(fold_report.to_markdown(index=False))
    lines.append("")

    lines.append("## Target (`ground_pm25`) distribution\n")
    lines.append("| Stat | Value |")
    lines.append("|---|---:|")
    for stat, val in target_stats.items():
        lines.append(f"| {stat} | {val:.2f} |")
    lines.append("")

    lines.append(f"## Features included ({len(feature_cols)})\n")
    for f in feature_cols:
        lines.append(f"- `{f}`")
    lines.append("")

    lines.append(f"## Final table\n\n- {len(training_table)} rows, {n_stations_final} distinct "
                  f"stations -> `{out_path.name}`\n")
    if n_stations_final < 8:
        lines.append(
            "**Caution:** fewer than 8 distinct stations remain. Spatial CV metrics from this few "
            "groups will be noisy -- report per-fold results individually in Stage 4, not just the "
            "mean, and treat model comparisons as indicative rather than conclusive."
        )

    (reports_dir / "training_table_summary.md").write_text("\n".join(lines) + "\n")

    print(f"Training table: {len(training_table)} rows, {n_stations_final} stations, "
          f"{len(feature_cols)} features -> {out_path}")
    print(f"CV strategy: {strategy}")
    print(f"Summary written to {reports_dir / 'training_table_summary.md'}")

    return training_table


def main():
    parser = argparse.ArgumentParser(description="Stage 3: feature / training dataset construction")
    parser.add_argument("--aligned-path", type=Path, default=config.ALIGNED_STATION_MONTHS_PATH)
    parser.add_argument("--out-dir", type=Path, default=config.PROCESSED_DATA_DIR)
    parser.add_argument("--reports-dir", type=Path, default=config.REPORTS_DIR)
    parser.add_argument("--meteorology", type=Path, default=None)
    parser.add_argument("--center-lat", type=float, default=None,
                         help="City centroid latitude, e.g. from the boundary polygon. Falls back "
                              "to the mean of station coordinates if omitted.")
    parser.add_argument("--center-lon", type=float, default=None)
    args = parser.parse_args()

    run(
        aligned_path=args.aligned_path, out_dir=args.out_dir, reports_dir=args.reports_dir,
        met_path=args.meteorology, center_lat=args.center_lat, center_lon=args.center_lon,
    )


if __name__ == "__main__":
    main()

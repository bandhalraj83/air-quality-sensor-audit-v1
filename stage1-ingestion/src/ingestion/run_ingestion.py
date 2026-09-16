"""
Stage 1 entry point.

Usage:
    python -m src.ingestion.run_ingestion
    python -m src.ingestion.run_ingestion --raw-dir data/raw --city Delhi

Loads all four sources, validates each, writes validated interim outputs
to data/interim/, and writes reports/data_quality_report.md.

Any single source failing to load (e.g. file not present yet) is caught and
reported rather than crashing the whole run -- useful while you're still
assembling the raw data package.
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, loaders, validators, report


def _try_run(label, fn):
    """Run fn(); on failure, print a clear message and return None instead of crashing."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 -- intentionally broad at the CLI boundary
        print(f"[FAILED] {label}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return None


def run(raw_dir: Path = None, interim_dir: Path = None, reports_dir: Path = None, city: str = None):
    raw_dir = Path(raw_dir or config.RAW_DATA_DIR)
    interim_dir = Path(interim_dir or config.INTERIM_DATA_DIR)
    reports_dir = Path(reports_dir or config.REPORTS_DIR)
    interim_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    results = []

    # --- CPCB stations ---------------------------------------------------
    def _cpcb():
        df = loaders.load_cpcb_stations(raw_dir / config.CPCB_STATIONS_PATH.name)
        result = validators.validate_cpcb_stations(df)
        result.df.to_parquet(interim_dir / "cpcb_stations_validated.parquet", index=False)
        print(f"CPCB: {result.n_records_in} stations loaded, "
              f"{sum(result.issues.values())} total flags raised.")
        return result

    r = _try_run("CPCB stations", _cpcb)
    if r:
        results.append(r)

    # --- OpenAQ ------------------------------------------------------------
    def _openaq():
        df = loaders.load_openaq(raw_dir / config.OPENAQ_PATH.name)
        result = validators.validate_openaq(df)
        result.df.to_parquet(interim_dir / "openaq_validated.parquet", index=False)
        print(f"OpenAQ: {result.n_records_in} PM2.5 records loaded, "
              f"{sum(v for k, v in result.issues.items() if k.startswith('_flag'))} flagged.")
        return result

    r = _try_run("OpenAQ archive", _openaq)
    if r:
        results.append(r)

    # --- SatPM ---------------------------------------------------------------
    def _satpm():
        ds = loaders.load_satpm(raw_dir / config.SATPM_PATH.name
                                 if (raw_dir / config.SATPM_PATH.name).exists()
                                 else raw_dir / "satpm")
        cleaned_ds, result = validators.validate_satpm(ds)
        cleaned_ds.to_netcdf(interim_dir / "satpm_validated.nc")
        print(f"SatPM: grid shape {result.shape}, "
              f"{result.issues.get('pct_out_of_range', 0)}% cells out of range.")
        return result

    r = _try_run("SatPM raster", _satpm)
    if r:
        results.append(r)

    # --- WorldPop --------------------------------------------------------
    def _worldpop():
        array, transform, crs = loaders.load_worldpop(raw_dir / config.WORLDPOP_PATH.name)
        cleaned, result = validators.validate_worldpop(array)
        np.save(interim_dir / "worldpop_validated.npy", cleaned)
        print(f"WorldPop: grid shape {result.shape}, "
              f"total population represented ~= {result.stats.get('total_population_sum', 0):,.0f}")
        return result

    r = _try_run("WorldPop raster", _worldpop)
    if r:
        results.append(r)

    # --- Report ------------------------------------------------------------
    if results:
        out_path = report.generate_data_quality_report(
            results, reports_dir / "data_quality_report.md", city=city
        )
        print(f"\nData-quality report written to {out_path}")
    else:
        print("\nNo sources loaded successfully -- check --raw-dir and file names in config.py.")

    return results


def main():
    parser = argparse.ArgumentParser(description="Stage 1: ingestion & validation")
    parser.add_argument("--raw-dir", type=Path, default=config.RAW_DATA_DIR)
    parser.add_argument("--interim-dir", type=Path, default=config.INTERIM_DATA_DIR)
    parser.add_argument("--reports-dir", type=Path, default=config.REPORTS_DIR)
    parser.add_argument("--city", type=str, default=None, help="City name, for report labeling")
    args = parser.parse_args()

    run(raw_dir=args.raw_dir, interim_dir=args.interim_dir, reports_dir=args.reports_dir, city=args.city)


if __name__ == "__main__":
    main()

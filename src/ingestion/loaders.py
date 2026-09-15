"""
Stage 1 -- source loaders.

Each function takes a raw file/directory path and returns a standard
internal shape:
    - CPCB stations, OpenAQ  -> pandas.DataFrame with canonical column names
    - SatPM                  -> xarray.Dataset with dims (time, lat, lon)
    - WorldPop                -> (numpy array, rasterio transform, crs string)

Loaders do NOT validate. That is validators.py's job -- keeping the two
separate means a loader failure ("file not found", "unreadable format") is
never confused with a validation failure ("value out of range").
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Union

import numpy as np
import pandas as pd

from . import config


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------
def _resolve_columns(df: pd.DataFrame, alias_map: Dict[str, List[str]]) -> pd.DataFrame:
    """
    Rename whatever columns are present in df to the canonical names in
    alias_map, matching case-insensitively and ignoring surrounding
    whitespace. Raises a clear error listing what was and wasn't found,
    rather than a downstream KeyError three functions later.
    """
    lower_lookup = {str(c).strip().lower(): c for c in df.columns}
    rename = {}
    missing = []
    for canonical, aliases in alias_map.items():
        found = next((lower_lookup[a] for a in aliases if a in lower_lookup), None)
        if found is not None:
            rename[found] = canonical
        else:
            missing.append(canonical)

    df = df.rename(columns=rename)
    if missing:
        # Not fatal here -- validators.py checks which of these are actually
        # required and reports it properly. We just make sure callers can see
        # what happened.
        df.attrs["unresolved_columns"] = missing
    return df


# ---------------------------------------------------------------------------
# CPCB station list
# ---------------------------------------------------------------------------
def load_cpcb_stations(path: Union[str, Path] = None) -> pd.DataFrame:
    path = Path(path or config.CPCB_STATIONS_PATH)
    if not path.exists():
        raise FileNotFoundError(f"CPCB station list not found at {path}")

    raw = pd.read_excel(path, engine="openpyxl")
    df = _resolve_columns(raw, config.CPCB_COLUMN_ALIASES)

    for col in ("latitude", "longitude"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["source"] = "CPCB"
    return df


# ---------------------------------------------------------------------------
# OpenAQ historical archive
# ---------------------------------------------------------------------------
def load_openaq(path: Union[str, Path] = None) -> pd.DataFrame:
    path = Path(path or config.OPENAQ_PATH)
    if not path.exists():
        raise FileNotFoundError(f"OpenAQ archive not found at {path}")

    if path.suffix.lower() == ".json":
        raw = pd.read_json(path)
    else:
        raw = pd.read_csv(path)

    df = _resolve_columns(raw, config.OPENAQ_COLUMN_ALIASES)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    for col in ("latitude", "longitude", "value"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Keep PM2.5 only -- OpenAQ archives are multi-pollutant.
    if "parameter" in df.columns:
        df = df[df["parameter"].astype(str).str.lower().isin(["pm25", "pm2.5"])].copy()

    df["source"] = "OpenAQ"
    return df


# ---------------------------------------------------------------------------
# SatPM V6 -- monthly satellite PM2.5
# ---------------------------------------------------------------------------
def load_satpm(path: Union[str, Path] = None):
    """
    Returns an xarray.Dataset with a 'pm25' variable on dims (time, lat, lon).

    Handles two possible packaging formats since the raw extract's exact
    layout isn't fixed yet:
      1. A single NetCDF file with a time dimension already present.
      2. A directory of monthly GeoTIFFs, one per month, with the month
         encoded in the filename as YYYY-MM or YYYYMM.
    """
    import xarray as xr

    path = Path(path or config.SATPM_PATH)
    if not path.exists():
        raise FileNotFoundError(f"SatPM data not found at {path}")

    if path.is_file():
        ds = xr.open_dataset(path)
        # Normalize variable name to 'pm25' if it arrived under another name
        if "pm25" not in ds.data_vars:
            candidates = [v for v in ds.data_vars if "pm" in v.lower()]
            if candidates:
                ds = ds.rename({candidates[0]: "pm25"})
        return ds

    # Directory of monthly GeoTIFFs
    import rioxarray  # noqa: F401  (registers the .rio accessor)

    tif_files = sorted(path.glob("*.tif")) + sorted(path.glob("*.tiff"))
    if not tif_files:
        raise FileNotFoundError(f"No .tif files found in SatPM directory {path}")

    date_pattern = re.compile(r"(\d{4})[-_]?(\d{2})")
    frames = []
    times = []
    for f in tif_files:
        match = date_pattern.search(f.stem)
        if not match:
            continue  # skip files we can't date -- validators.py will report the gap
        year, month = match.groups()
        da = xr.open_dataarray(f, engine="rasterio").squeeze(drop=True)
        frames.append(da)
        times.append(pd.Timestamp(f"{year}-{month}-01"))

    if not frames:
        raise ValueError(f"Found .tif files in {path} but none matched a YYYY-MM date pattern")

    stacked = xr.concat(frames, dim=pd.Index(times, name="time"))
    return stacked.to_dataset(name="pm25")


# ---------------------------------------------------------------------------
# WorldPop 100m population grid
# ---------------------------------------------------------------------------
def load_worldpop(path: Union[str, Path] = None):
    """
    Returns (array, transform, crs). Kept as raw rasterio objects (rather
    than xarray) since Stage 2 needs the affine transform directly for
    resampling/reprojection.
    """
    import rasterio

    path = Path(path or config.WORLDPOP_PATH)
    if not path.exists():
        raise FileNotFoundError(f"WorldPop raster not found at {path}")

    with rasterio.open(path) as src:
        array = src.read(1).astype("float32")
        nodata = src.nodata
        if nodata is not None:
            array = np.where(array == nodata, np.nan, array)
        transform = src.transform
        crs = src.crs.to_string() if src.crs else None

    return array, transform, crs

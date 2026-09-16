"""
Stage 1 -- validation.

Philosophy: FLAG, don't silently delete. Every tabular validator adds
boolean `_flag_*` columns to the dataframe rather than dropping rows, and
returns a ValidationResult summarizing counts. Stage 2+ can call
`drop_flagged()` if it wants a strictly clean frame, but the flagged rows
stay auditable in the interim data and in the data-quality report -- an
examiner asking "how many records did you throw away, and why" should be
answerable from the report, not from memory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import config


@dataclass
class ValidationResult:
    source: str
    n_records_in: int
    n_records_out: int
    issues: Dict[str, int] = field(default_factory=dict)   # check name -> flagged count
    notes: List[str] = field(default_factory=list)
    df: Optional[pd.DataFrame] = None   # None for raster sources -- see raster results below


@dataclass
class RasterValidationResult:
    source: str
    shape: tuple
    issues: Dict[str, int] = field(default_factory=dict)
    stats: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Generic, reusable checks (tabular)
# ---------------------------------------------------------------------------
def check_schema(df: pd.DataFrame, required_cols: List[str]) -> List[str]:
    """Returns the list of required columns that are missing."""
    return [c for c in required_cols if c not in df.columns]


def flag_missing(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    present_cols = [c for c in cols if c in df.columns]
    if not present_cols:
        return pd.Series(True, index=df.index)  # everything's missing if the column doesn't exist
    return df[present_cols].isna().any(axis=1)


def flag_out_of_range(df: pd.DataFrame, col: str, vmin: float, vmax: float) -> pd.Series:
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    values = pd.to_numeric(df[col], errors="coerce")
    return (values < vmin) | (values > vmax) | values.isna()


def flag_out_of_bbox(df: pd.DataFrame, lat_col: str, lon_col: str, bbox: dict) -> pd.Series:
    if lat_col not in df.columns or lon_col not in df.columns:
        return pd.Series(True, index=df.index)
    lat = pd.to_numeric(df[lat_col], errors="coerce")
    lon = pd.to_numeric(df[lon_col], errors="coerce")
    return (
        lat.isna() | lon.isna()
        | (lat < bbox["lat_min"]) | (lat > bbox["lat_max"])
        | (lon < bbox["lon_min"]) | (lon > bbox["lon_max"])
    )


def flag_duplicates(df: pd.DataFrame, subset: List[str]) -> pd.Series:
    present = [c for c in subset if c in df.columns]
    if not present:
        return pd.Series(False, index=df.index)
    return df.duplicated(subset=present, keep="first")


def monthly_completeness(df: pd.DataFrame, group_col: str, date_col: str) -> pd.DataFrame:
    """
    For each group (station) and month, what fraction of calendar days had
    at least one reading. Used to decide, later, which station-months are
    reliable enough to feed Stage 3's training table.
    """
    if group_col not in df.columns or date_col not in df.columns:
        return pd.DataFrame(columns=[group_col, "month", "days_reported", "days_in_month", "completeness"])

    d = df.dropna(subset=[date_col]).copy()
    date_series = d[date_col]
    if pd.api.types.is_datetime64tz_dtype(date_series):
        date_series = date_series.dt.tz_convert(None)
    d["month"] = date_series.dt.to_period("M")
    d["day"] = d[date_col].dt.date

    grouped = (
        d.groupby([group_col, "month"])["day"]
        .nunique()
        .reset_index(name="days_reported")
    )
    grouped["days_in_month"] = grouped["month"].apply(lambda p: p.days_in_month)
    grouped["completeness"] = grouped["days_reported"] / grouped["days_in_month"]
    return grouped


def drop_flagged(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience for downstream stages that want a strictly clean frame."""
    flag_cols = [c for c in df.columns if c.startswith("_flag_")]
    if not flag_cols:
        return df
    keep_mask = ~df[flag_cols].any(axis=1)
    return df.loc[keep_mask].drop(columns=flag_cols)


# ---------------------------------------------------------------------------
# Per-source validators
# ---------------------------------------------------------------------------
def validate_cpcb_stations(df: pd.DataFrame) -> ValidationResult:
    n_in = len(df)
    issues = {}
    notes = []

    missing_required = check_schema(df, config.CPCB_REQUIRED)
    if missing_required:
        notes.append(f"Missing required columns: {missing_required}")

    df = df.copy()
    df["_flag_missing_coords"] = flag_missing(df, ["latitude", "longitude"])
    df["_flag_out_of_bbox"] = flag_out_of_bbox(df, "latitude", "longitude", config.INDIA_BBOX)
    df["_flag_duplicate_station"] = flag_duplicates(df, ["station_id"])
    df["_flag_duplicate_location"] = flag_duplicates(df, ["latitude", "longitude"])

    for c in ["_flag_missing_coords", "_flag_out_of_bbox", "_flag_duplicate_station", "_flag_duplicate_location"]:
        issues[c] = int(df[c].sum())

    if df.get("_flag_duplicate_location", pd.Series(dtype=bool)).sum() > 0:
        notes.append(
            "Some stations share identical coordinates -- check whether these are "
            "genuinely co-located instruments or a lat/lon entry error."
        )

    return ValidationResult(
        source="CPCB",
        n_records_in=n_in,
        n_records_out=len(df),
        issues=issues,
        notes=notes,
        df=df,
    )


def validate_openaq(df: pd.DataFrame) -> ValidationResult:
    n_in = len(df)
    issues = {}
    notes = []

    missing_required = check_schema(df, config.OPENAQ_REQUIRED)
    if missing_required:
        notes.append(f"Missing required columns: {missing_required}")

    df = df.copy()
    df["_flag_missing_core"] = flag_missing(df, ["location_id", "latitude", "longitude", "value", "date"])
    df["_flag_out_of_bbox"] = flag_out_of_bbox(df, "latitude", "longitude", config.INDIA_BBOX)
    df["_flag_out_of_range"] = flag_out_of_range(df, "value", config.PM25_MIN, config.PM25_MAX)
    df["_flag_duplicate"] = flag_duplicates(df, ["location_id", "date", "parameter"])

    for c in ["_flag_missing_core", "_flag_out_of_bbox", "_flag_out_of_range", "_flag_duplicate"]:
        issues[c] = int(df[c].sum())

    completeness = monthly_completeness(df, "location_id", "date")
    low_completeness_station_months = int((completeness["completeness"] < config.MIN_MONTHLY_COMPLETENESS).sum())
    issues["station_months_below_completeness_threshold"] = low_completeness_station_months
    notes.append(
        f"{low_completeness_station_months} of {len(completeness)} station-months fall below the "
        f"{config.MIN_MONTHLY_COMPLETENESS:.0%} daily-completeness threshold "
        f"(kept, but Stage 3 should treat them cautiously or exclude them)."
    )

    return ValidationResult(
        source="OpenAQ",
        n_records_in=n_in,
        n_records_out=len(df),
        issues=issues,
        notes=notes,
        df=df,
    )


def validate_satpm(ds, mask_invalid: bool = True):
    """
    ds: xarray.Dataset with a 'pm25' variable on (time, lat, lon) or similar.
    Returns (cleaned_ds, RasterValidationResult).
    """
    issues = {}
    notes = []

    if "pm25" not in ds.data_vars:
        notes.append("No 'pm25' variable found after loading -- check SatPM variable naming.")
        return ds, RasterValidationResult(source="SatPM", shape=(), issues=issues, notes=notes)

    values = ds["pm25"].values
    n_total = values.size
    n_nan_in = int(np.isnan(values).sum())
    out_of_range = (values < config.PM25_MIN) | (values > config.PM25_MAX)
    n_out_of_range = int(np.nansum(out_of_range))

    issues["n_nan"] = n_nan_in
    issues["pct_nan"] = round(100 * n_nan_in / n_total, 3) if n_total else 0.0
    issues["n_out_of_range"] = n_out_of_range
    issues["pct_out_of_range"] = round(100 * n_out_of_range / n_total, 3) if n_total else 0.0

    if mask_invalid:
        values = np.where(out_of_range, np.nan, values)
        ds = ds.assign(pm25=(ds["pm25"].dims, values))

    if "time" in ds.coords:
        months = pd.to_datetime(ds["time"].values)
        notes.append(f"Time coverage: {months.min().date()} to {months.max().date()} ({len(months)} months).")

    stats = {
        "min": float(np.nanmin(values)) if n_total else float("nan"),
        "max": float(np.nanmax(values)) if n_total else float("nan"),
        "mean": float(np.nanmean(values)) if n_total else float("nan"),
    }

    return ds, RasterValidationResult(
        source="SatPM", shape=values.shape, issues=issues, notes=notes, stats=stats
    )


def validate_worldpop(array: np.ndarray, mask_invalid: bool = True):
    """Returns (cleaned_array, RasterValidationResult)."""
    issues = {}
    notes = []

    n_total = array.size
    n_nan_in = int(np.isnan(array).sum())
    out_of_range = (array < config.POPULATION_MIN) | (array > config.POPULATION_MAX)
    n_out_of_range = int(np.nansum(out_of_range))

    issues["n_nodata"] = n_nan_in
    issues["pct_nodata"] = round(100 * n_nan_in / n_total, 3) if n_total else 0.0
    issues["n_out_of_range"] = n_out_of_range
    issues["pct_out_of_range"] = round(100 * n_out_of_range / n_total, 3) if n_total else 0.0

    cleaned = array.copy()
    if mask_invalid:
        cleaned = np.where(out_of_range, np.nan, cleaned)

    stats = {
        "min": float(np.nanmin(cleaned)) if n_total else float("nan"),
        "max": float(np.nanmax(cleaned)) if n_total else float("nan"),
        "total_population_sum": float(np.nansum(cleaned)),
    }
    notes.append(
        f"Sum of all valid pixel values ~= total population represented in this raster "
        f"({stats['total_population_sum']:,.0f}); sanity-check this against the city's known population."
    )

    return cleaned, RasterValidationResult(
        source="WorldPop", shape=array.shape, issues=issues, notes=notes, stats=stats
    )

"""
Temporal alignment -- collapse OpenAQ's daily/hourly readings down to
monthly means so they're on the same time unit as SatPM's monthly grids.
"""
from __future__ import annotations

import pandas as pd

from . import config


def aggregate_openaq_monthly(df: pd.DataFrame, min_completeness: float = None,
                              use_flagged_rows: bool = False) -> pd.DataFrame:
    """
    df: OpenAQ validated DataFrame from Stage 1 (has _flag_* columns).

    By default, rows flagged in Stage 1 as missing-core-fields, out-of-range,
    or duplicate are excluded before aggregating (use_flagged_rows=True keeps
    them, useful for sensitivity checks). Out-of-bbox rows are always
    excluded -- a station outside India isn't a station in this city.

    Returns a station-month table: location_id, month, mean_pm25,
    days_reported, days_in_month, completeness, reliable.
    """
    min_completeness = min_completeness if min_completeness is not None else config.MIN_MONTHLY_COMPLETENESS

    d = df.copy()
    if not use_flagged_rows:
        drop_cols = [c for c in ["_flag_missing_core", "_flag_out_of_range", "_flag_duplicate"] if c in d.columns]
        if drop_cols:
            d = d.loc[~d[drop_cols].any(axis=1)]
    if "_flag_out_of_bbox" in d.columns:
        d = d.loc[~d["_flag_out_of_bbox"]]

    d = d.dropna(subset=["date", "value", "location_id"])

    date_series = d["date"]
    if pd.api.types.is_datetime64tz_dtype(date_series):
        date_series = date_series.dt.tz_convert(None)
    d = d.assign(month=date_series.dt.to_period("M"), day=date_series.dt.date)

    grouped = d.groupby(["location_id", "month"]).agg(
        mean_pm25=("value", "mean"),
        days_reported=("day", "nunique"),
        latitude=("latitude", "first"),
        longitude=("longitude", "first"),
    ).reset_index()

    grouped["days_in_month"] = grouped["month"].apply(lambda p: p.days_in_month)
    grouped["completeness"] = grouped["days_reported"] / grouped["days_in_month"]
    grouped["reliable"] = grouped["completeness"] >= min_completeness

    return grouped

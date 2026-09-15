"""
Stage 3 -- feature engineering.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd


def add_month_cyclical(df: pd.DataFrame, month_col: str = "month") -> pd.DataFrame:
    """
    Encodes calendar month as (sin, cos) rather than a raw 1-12 integer, so
    a model sees December and January as adjacent rather than maximally far
    apart -- a real effect for PM2.5, which has a strong winter/summer cycle
    in most Indian cities.
    """
    df = df.copy()
    month_num = pd.PeriodIndex(df[month_col].astype(str), freq="M").month
    df["month_sin"] = np.sin(2 * np.pi * month_num / 12)
    df["month_cos"] = np.cos(2 * np.pi * month_num / 12)
    return df


def add_distance_to_city_center(df: pd.DataFrame, lat_col: str = "latitude", lon_col: str = "longitude",
                                 center_lat: float = None, center_lon: float = None) -> pd.DataFrame:
    """
    Great-circle distance (km) from each station to a city-center point.
    If center_lat/lon aren't supplied, falls back to the centroid of the
    stations present in df -- workable, but pass the real city/boundary
    centroid when you have one for a more meaningful covariate.
    """
    df = df.copy()
    if center_lat is None or center_lon is None:
        center_lat = df[lat_col].mean()
        center_lon = df[lon_col].mean()

    R = 6371.0
    lat1, lon1 = np.radians(df[lat_col]), np.radians(df[lon_col])
    lat2, lon2 = np.radians(center_lat), np.radians(center_lon)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    df["distance_to_city_center_km"] = 2 * R * np.arcsin(np.sqrt(a))
    return df


def impute_missing_covariates(df: pd.DataFrame, numeric_cols: list, categorical_cols: list) -> pd.DataFrame:
    """
    Median imputation for numeric covariates, 'Unknown' category for
    categoricals. Deliberately does NOT impute satellite_pm25 or the
    target -- those get dropped upstream (config.DROP_IF_MISSING_*), not
    filled in, since imputing the thing you're trying to model is a much
    bigger methodological problem than imputing a secondary covariate.
    """
    df = df.copy()
    for col in numeric_cols:
        if col in df.columns and col not in ("satellite_pm25",) and df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown").astype(str)
    return df


def merge_meteorology(df: pd.DataFrame, met_path: Union[str, Path, None]) -> pd.DataFrame:
    """
    Optional hook. If you add meteorological covariates (e.g. ERA5
    temperature/wind speed/boundary-layer height extracted at station
    locations), save them as a CSV with columns station_id, month, and
    whatever met variables you have, and pass --meteorology on the CLI.
    Not required for the core pipeline to run.
    """
    if met_path is None:
        return df
    met = pd.read_csv(met_path)
    met["month"] = pd.PeriodIndex(met["month"].astype(str), freq="M")
    df = df.copy()
    df["month"] = pd.PeriodIndex(df["month"].astype(str), freq="M")
    return df.merge(met, on=["station_id", "month"], how="left")


def one_hot_encode(df: pd.DataFrame, categorical_cols: list) -> pd.DataFrame:
    present = [c for c in categorical_cols if c in df.columns]
    if not present:
        return df
    return pd.get_dummies(df, columns=present, prefix=present)

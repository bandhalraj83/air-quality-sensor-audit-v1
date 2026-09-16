"""
Station-pixel join -- for every ground station, look up the underlying
raster value(s) at its exact coordinate. This is what lets Stage 3 build a
(satellite estimate, ground truth) training pair per station-month.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pyproj
from affine import Affine


def _lonlat_to_pixel(lons, lats, transform: Affine, raster_crs: str):
    """Converts WGS84 lon/lat arrays to (row, col) pixel indices in the raster's CRS/grid."""
    transformer = pyproj.Transformer.from_crs("EPSG:4326", raster_crs, always_xy=True)
    xs, ys = transformer.transform(np.asarray(lons), np.asarray(lats))
    inv = ~transform
    cols, rows = inv * (xs, ys)
    return np.round(rows).astype(int), np.round(cols).astype(int)


def sample_raster_at_points(array: np.ndarray, transform: Affine, crs: str, points_df: pd.DataFrame,
                             lat_col: str = "latitude", lon_col: str = "longitude") -> pd.Series:
    """
    Single-band raster (e.g. WorldPop). Returns a Series aligned to
    points_df.index; NaN for any point that falls outside the raster extent.
    """
    rows, cols = _lonlat_to_pixel(points_df[lon_col].values, points_df[lat_col].values, transform, crs)
    height, width = array.shape

    values = np.full(len(points_df), np.nan, dtype="float64")
    in_bounds = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
    values[in_bounds] = array[rows[in_bounds], cols[in_bounds]]

    return pd.Series(values, index=points_df.index)


def sample_raster_stack_at_points(stack: np.ndarray, times, transform: Affine, crs: str,
                                   points_df: pd.DataFrame, station_id_col: str = "station_id",
                                   lat_col: str = "latitude", lon_col: str = "longitude") -> pd.DataFrame:
    """
    Multi-band raster stack (e.g. SatPM, dims [time, lat, lon]). Returns a
    long-format DataFrame with one row per station per time step:
    station_id_col, month, satellite_pm25.
    """
    rows, cols = _lonlat_to_pixel(points_df[lon_col].values, points_df[lat_col].values, transform, crs)
    height, width = stack.shape[1], stack.shape[2]
    in_bounds = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)

    records = []
    for t_idx, t in enumerate(times):
        band = stack[t_idx]
        vals = np.full(len(points_df), np.nan, dtype="float64")
        vals[in_bounds] = band[rows[in_bounds], cols[in_bounds]]
        for i, station_id in enumerate(points_df[station_id_col].values):
            records.append({
                station_id_col: station_id,
                "month": pd.Timestamp(t).to_period("M"),
                "satellite_pm25": vals[i],
            })
    return pd.DataFrame(records)

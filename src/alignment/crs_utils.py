"""
CRS utilities -- picking a local projected CRS and reprojecting rasters
onto it. Every function here is deliberately generic (no hardcoded city or
zone) so the same code works whichever city you point it at.
"""
from __future__ import annotations

import numpy as np
from affine import Affine
from pyproj import CRS
from rasterio.warp import Resampling, calculate_default_transform, reproject


def utm_crs_for_bbox(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> str:
    """
    Returns the EPSG code (as 'EPSG:XXXX') of the UTM zone covering the
    centroid of the given lon/lat bounding box. This is what every
    distance-based operation (resampling, clipping, point-sampling) should
    be done in -- lat/lon degrees are not equal-area or equal-distance, so
    IDW/kriging/pixel-area math done directly in degrees is subtly wrong.
    """
    center_lon = (lon_min + lon_max) / 2
    center_lat = (lat_min + lat_max) / 2
    zone = int((center_lon + 180) / 6) + 1
    hemisphere = 326 if center_lat >= 0 else 327  # EPSG 326xx = N, 327xx = S
    epsg = hemisphere * 100 + zone
    return f"EPSG:{epsg}"


def reproject_array(
    array: np.ndarray,
    src_transform: Affine,
    src_crs: str,
    dst_crs: str,
    dst_transform: Affine = None,
    dst_shape: tuple = None,
    resampling: str = "bilinear",
):
    """
    Reprojects a single-band array from (src_transform, src_crs) into
    dst_crs. If dst_transform/dst_shape aren't given, they're computed
    automatically to cover the same extent at native resolution -- pass
    them explicitly (e.g. from build_common_grid) to snap onto a shared
    analysis grid instead.

    resampling: 'bilinear' for continuous fields (PM2.5, population density),
                'nearest' for categorical data. Never 'bilinear' for
                population *counts* you plan to sum -- see grid.py's note
                on that.
    """
    resampling_enum = getattr(Resampling, resampling)

    if dst_transform is None or dst_shape is None:
        dst_transform, width, height = calculate_default_transform(
            src_crs, dst_crs, array.shape[1], array.shape[0],
            *_bounds_from_transform(src_transform, array.shape),
        )
        dst_shape = (height, width)

    dst_array = np.full(dst_shape, np.nan, dtype="float32")
    reproject(
        source=array,
        destination=dst_array,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=resampling_enum,
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )
    return dst_array, dst_transform


def bounds_from_transform(transform: Affine, shape: tuple):
    height, width = shape
    left, top = transform * (0, 0)
    right, bottom = transform * (width, height)
    return (min(left, right), min(top, bottom), max(left, right), max(top, bottom))


# Kept for internal backward-compatible use within this module.
_bounds_from_transform = bounds_from_transform

"""
Common analysis grid -- one shared pixel grid (extent, resolution, CRS) that
SatPM and WorldPop both get resampled onto, so later stages can do direct
pixel-to-pixel arithmetic (PM2.5[i] * Population[i]) without alignment bugs.
"""
from __future__ import annotations

import numpy as np
import pyproj
from affine import Affine

from . import crs_utils


def build_common_grid(bbox: dict, target_crs: str, resolution_m: float):
    """
    bbox: dict with lon_min/lat_min/lon_max/lat_max (WGS84), typically from
    boundary.bbox_of(). Returns (transform, width, height) in target_crs.
    """
    transformer = pyproj.Transformer.from_crs("EPSG:4326", target_crs, always_xy=True)
    x_min, y_min = transformer.transform(bbox["lon_min"], bbox["lat_min"])
    x_max, y_max = transformer.transform(bbox["lon_max"], bbox["lat_max"])

    # Small padding so edge pixels of the city aren't clipped by a rounding sliver.
    pad = resolution_m * 2
    x_min, y_min, x_max, y_max = x_min - pad, y_min - pad, x_max + pad, y_max + pad

    width = int(np.ceil((x_max - x_min) / resolution_m))
    height = int(np.ceil((y_max - y_min) / resolution_m))
    transform = Affine.translation(x_min, y_max) * Affine.scale(resolution_m, -resolution_m)

    return transform, width, height


def resample_concentration(array, src_transform, src_crs, dst_transform, dst_shape, dst_crs):
    """
    For intensive fields (PM2.5 concentration, and anything else where the
    *value* at a point stays meaningful regardless of pixel size) --
    bilinear interpolation, no further correction needed.
    """
    return crs_utils.reproject_array(
        array, src_transform, src_crs, dst_crs, dst_transform, dst_shape, resampling="bilinear"
    )


def resample_population_preserving_total(array, src_transform, src_crs, dst_transform, dst_shape, dst_crs):
    """
    For extensive fields (population *counts*, where the total across all
    pixels is what should stay meaningful) -- resamples with bilinear
    interpolation, then rescales so the destination grid's total matches
    the *source raster's total over that same ground footprint* -- not the
    source raster's grand total, which would be wrong any time the source
    covers more area than the destination (e.g. a nationwide WorldPop
    raster being resampled down to one city's extent).

    Reprojection alone can quietly inflate or deflate total population
    because source and destination pixels rarely cover exactly the same
    ground area; this correction keeps Stage 5's population-weighted
    exposure numbers honest.
    """
    from rasterio.windows import from_bounds as window_from_bounds

    # Where does the destination grid's footprint fall in the source raster?
    dst_bounds = crs_utils.bounds_from_transform(dst_transform, dst_shape)
    transformer = pyproj.Transformer.from_crs(dst_crs, src_crs, always_xy=True)
    corner_xs = [dst_bounds[0], dst_bounds[2], dst_bounds[0], dst_bounds[2]]
    corner_ys = [dst_bounds[1], dst_bounds[1], dst_bounds[3], dst_bounds[3]]
    src_xs, src_ys = transformer.transform(corner_xs, corner_ys)
    src_bounds = (min(src_xs), min(src_ys), max(src_xs), max(src_ys))

    window = window_from_bounds(*src_bounds, transform=src_transform)
    row_start = max(int(np.floor(window.row_off)), 0)
    col_start = max(int(np.floor(window.col_off)), 0)
    row_stop = min(int(np.ceil(window.row_off + window.height)), array.shape[0])
    col_stop = min(int(np.ceil(window.col_off + window.width)), array.shape[1])

    if row_stop > row_start and col_stop > col_start:
        matching_footprint_total = float(np.nansum(array[row_start:row_stop, col_start:col_stop]))
    else:
        matching_footprint_total = 0.0  # destination doesn't overlap source at all

    resampled, transform = crs_utils.reproject_array(
        array, src_transform, src_crs, dst_crs, dst_transform, dst_shape, resampling="bilinear"
    )
    resampled_total = float(np.nansum(resampled))
    if resampled_total > 0 and matching_footprint_total > 0:
        scale_factor = matching_footprint_total / resampled_total
        resampled = resampled * scale_factor
    return resampled, transform

"""
Clip an aligned raster array down to the city boundary, and crop its extent
tightly to the boundary's bounding box so downstream stages aren't carrying
around a mostly-empty grid.
"""
from __future__ import annotations

import numpy as np
from affine import Affine
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds


def clip_to_boundary(array: np.ndarray, transform: Affine, crs: str, boundary_gdf):
    """
    array/transform/crs: a single-band raster already on the common grid.
    boundary_gdf: GeoDataFrame (any CRS -- reprojected internally to `crs`).

    Returns (clipped_array, clipped_transform), cropped to the boundary's
    bounding box with pixels outside the polygon set to NaN.
    """
    boundary_proj = boundary_gdf.to_crs(crs)
    geoms = [geom.__geo_interface__ for geom in boundary_proj.geometry]

    # True outside the polygon by default; invert so True = keep.
    outside_mask = geometry_mask(geoms, out_shape=array.shape, transform=transform, invert=False)
    masked = np.where(outside_mask, np.nan, array)

    minx, miny, maxx, maxy = boundary_proj.total_bounds
    window = from_bounds(minx, miny, maxx, maxy, transform=transform)

    row_start = max(int(np.floor(window.row_off)), 0)
    col_start = max(int(np.floor(window.col_off)), 0)
    row_stop = min(int(np.ceil(window.row_off + window.height)), array.shape[0])
    col_stop = min(int(np.ceil(window.col_off + window.width)), array.shape[1])

    if row_stop <= row_start or col_stop <= col_start:
        raise ValueError(
            "Boundary does not overlap the raster after reprojection -- "
            "check that the boundary file actually covers the target city."
        )

    cropped = masked[row_start:row_stop, col_start:col_stop]
    cropped_transform = transform * Affine.translation(col_start, row_start)

    return cropped, cropped_transform

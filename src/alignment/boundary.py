"""
City/ward boundary loading.

The raw data package doesn't include a boundary polygon (see the
architecture doc's caveats) -- source one from GADM (gadm.org) or Bhuvan
before running this for real, save it as GeoJSON, and point
config.BOUNDARY_PATH at it. This module just loads and validates whatever's
there.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

import geopandas as gpd


def load_boundary(path: Union[str, Path], dissolve: bool = True) -> gpd.GeoDataFrame:
    """
    Loads a city (or ward) boundary file. If dissolve=True and the file has
    multiple polygons (e.g. one row per ward), they're merged into a single
    city-outline polygon for the Stage 2 clip step -- keep dissolve=False if
    you specifically want to retain ward boundaries for ward-level Stage 5/6
    aggregation later.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"No boundary file at {path}. This isn't part of the raw data "
            f"package -- source one from GADM (gadm.org) or Bhuvan, save as "
            f"GeoJSON, and point config.BOUNDARY_PATH at it."
        )

    gdf = gpd.read_file(path)
    if gdf.crs is None:
        raise ValueError(f"Boundary file {path} has no CRS defined -- fix the source file.")
    if gdf.crs.to_string() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    if dissolve and len(gdf) > 1:
        gdf = gdf.dissolve().reset_index(drop=True)

    return gdf


def bbox_of(gdf: gpd.GeoDataFrame) -> dict:
    minx, miny, maxx, maxy = gdf.total_bounds
    return dict(lon_min=minx, lat_min=miny, lon_max=maxx, lat_max=maxy)

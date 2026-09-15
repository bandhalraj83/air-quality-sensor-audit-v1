"""
Generates a stand-in city boundary polygon (a rough circle) covering the
same bounding box used by tests/make_sample_raw_data.py, so Stage 2 can be
tested end-to-end before a real GADM/Bhuvan boundary is sourced.

Usage:
    python tests/make_sample_boundary.py [--out data/raw/city_boundary.geojson]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

# Must match tests/make_sample_raw_data.py's LAT_RANGE / LON_RANGE
LAT_RANGE = (28.40, 28.80)
LON_RANGE = (76.85, 77.35)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("data/raw/city_boundary.geojson"))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    center_lat = sum(LAT_RANGE) / 2
    center_lon = sum(LON_RANGE) / 2
    radius_deg = min(LAT_RANGE[1] - LAT_RANGE[0], LON_RANGE[1] - LON_RANGE[0]) / 2 * 0.85

    circle = Point(center_lon, center_lat).buffer(radius_deg, resolution=32)
    gdf = gpd.GeoDataFrame({"name": ["sample_city"]}, geometry=[circle], crs="EPSG:4326")
    gdf.to_file(args.out, driver="GeoJSON")
    print(f"Wrote synthetic boundary polygon -> {args.out}")


if __name__ == "__main__":
    main()

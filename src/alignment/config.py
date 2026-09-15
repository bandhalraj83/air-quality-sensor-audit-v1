"""
Configuration for Stage 2 -- Spatial & Temporal Alignment.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTERIM_DATA_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

# City/ward boundary polygon -- NOT part of the raw data package (see the
# architecture doc). Point this at a GeoJSON or shapefile with one polygon
# (or dissolve to one) covering the target city before running Stage 2 for
# real. tests/make_sample_boundary.py builds a stand-in for testing.
BOUNDARY_PATH = PROJECT_ROOT / "data" / "raw" / "city_boundary.geojson"

# ---------------------------------------------------------------------------
# CRS strategy
# ---------------------------------------------------------------------------
# Storage / interop CRS -- what gets written to disk and what SatPM/WorldPop
# are assumed to already be in in the absence of other metadata.
STORAGE_CRS = "EPSG:4326"

# Every distance-based operation (resampling to a metric grid, clipping,
# point sampling in meters) happens in a *projected*, roughly-equal-area CRS
# local to the city, not in lat/lon degrees. crs_utils.utm_crs_for_bbox()
# picks the right UTM zone automatically from the city's coordinates -- no
# need to hardcode a zone here.

# ---------------------------------------------------------------------------
# Common analysis grid
# ---------------------------------------------------------------------------
ANALYSIS_RESOLUTION_M = 100   # matches WorldPop's native resolution

# ---------------------------------------------------------------------------
# Temporal alignment
# ---------------------------------------------------------------------------
MIN_MONTHLY_COMPLETENESS = 0.5   # must match Stage 1's threshold for consistency

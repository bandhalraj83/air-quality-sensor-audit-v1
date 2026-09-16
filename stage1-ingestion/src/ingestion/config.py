"""
Configuration for Stage 1 -- Ingestion & Validation.

Edit RAW_DATA_DIR (or pass --raw-dir on the CLI) to point at wherever the
project package's raw extracts live. Everything else -- column aliases,
plausible value ranges, required fields -- is tuned here so loaders and
validators never need touching just because a source's column names differ.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DATA_DIR = PROJECT_ROOT / "data" / "interim"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Expected raw file names. SatPM may arrive as a single NetCDF file OR as a
# directory of monthly GeoTIFFs -- loaders.load_satpm() handles either.
CPCB_STATIONS_PATH = RAW_DATA_DIR / "cpcb_caaqms_stations.xlsx"
SATPM_PATH = RAW_DATA_DIR / "satpm_v6_pm25.nc"
WORLDPOP_PATH = RAW_DATA_DIR / "worldpop_india_100m.tif"
OPENAQ_PATH = RAW_DATA_DIR / "openaq_historical_archive.csv"

# ---------------------------------------------------------------------------
# India bounding box (rough, with a little slack) -- sanity check for coords
# ---------------------------------------------------------------------------
INDIA_BBOX = dict(lat_min=6.0, lat_max=37.5, lon_min=68.0, lon_max=97.5)

# ---------------------------------------------------------------------------
# Plausible physical ranges. Stage 1's job is to FLAG values outside these,
# not silently delete them -- deletions are a modeling-stage decision.
# ---------------------------------------------------------------------------
PM25_MIN, PM25_MAX = 0.0, 1000.0   # ug/m3; CPCB has recorded >900 in severe events
POPULATION_MIN, POPULATION_MAX = 0.0, 50_000.0  # people per 100m cell -- generous upper bound

# Minimum fraction of days in a month a station must report to be considered
# a usable station-month later in Stage 2/3. Computed and flagged here.
MIN_MONTHLY_COMPLETENESS = 0.5

# ---------------------------------------------------------------------------
# Column aliases -- real extracts rarely match a clean schema on the first
# try. Each canonical field maps to a list of lowercased alternatives that
# loaders will search for, in order.
# ---------------------------------------------------------------------------
CPCB_COLUMN_ALIASES = {
    "station_id": ["station_id", "station code", "stationid", "s.no", "sno", "id"],
    "station_name": ["station_name", "station name", "monitoring station", "name"],
    "city": ["city", "city/town/village/area", "location"],
    "state": ["state"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "long", "lon", "lng"],
    "station_type": ["station_type", "type", "site type", "agency"],
}
CPCB_REQUIRED = ["station_id", "city", "latitude", "longitude"]

OPENAQ_COLUMN_ALIASES = {
    "location_id": ["location_id", "locationid", "location"],
    "city": ["city"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "lng"],
    "parameter": ["parameter", "pollutant"],
    "value": ["value", "measurement"],
    "unit": ["unit", "units"],
    "date": ["date", "datetime", "date_utc", "date_local", "timestamp"],
}
OPENAQ_REQUIRED = ["location_id", "latitude", "longitude", "parameter", "value", "date"]

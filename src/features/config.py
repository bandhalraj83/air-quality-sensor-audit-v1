"""
Configuration for Stage 3 -- Feature / Training Dataset construction.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"

ALIGNED_STATION_MONTHS_PATH = PROCESSED_DATA_DIR / "aligned_station_months.parquet"

# Optional -- a CSV of meteorological covariates to merge in, keyed by
# station_id (or lat/lon) and month. Not part of the raw data package; see
# engineer.merge_meteorology() for the expected shape. Leave unset to skip.
METEOROLOGY_PATH = None

# ---------------------------------------------------------------------------
# Filtering -- what makes a station-month usable for training
# ---------------------------------------------------------------------------
REQUIRE_RELIABLE_COMPLETENESS = True   # use Stage 2's `reliable` flag (>=50% days reported)
DROP_IF_MISSING_SATELLITE = True
DROP_IF_MISSING_GROUND_TRUTH = True

# ---------------------------------------------------------------------------
# Feature columns fed to Stage 4's models. Kept explicit (rather than "use
# every column") so it's obvious what the model does and doesn't see, and so
# adding a real meteorology merge later is a one-line change here.
# ---------------------------------------------------------------------------
NUMERIC_FEATURES = [
    "satellite_pm25",
    "population_at_station",
    "distance_to_city_center_km",
    "month_sin",
    "month_cos",
]
CATEGORICAL_FEATURES = ["station_type"]
TARGET_COLUMN = "ground_pm25"
GROUP_COLUMN = "station_id"   # what spatial CV groups on

# ---------------------------------------------------------------------------
# Spatial cross-validation
# ---------------------------------------------------------------------------
# Below this many distinct stations, leave-one-station-out is used instead
# of k-fold, since k-fold with very few groups gives unstable, misleading
# per-fold metrics.
MIN_STATIONS_FOR_KFOLD = 15
DEFAULT_N_SPLITS = 5

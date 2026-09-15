# Stage 1 — Ingestion & Validation

Loads the four raw sources (CPCB station list, OpenAQ archive, SatPM PM2.5, WorldPop),
validates each, and writes:
- validated interim data to `data/interim/`
- a data-quality report to `reports/data_quality_report.md`

Nothing is silently dropped. Tabular sources get boolean `_flag_*` columns added;
raster sources get invalid cells masked to NaN and counted. Call
`validators.drop_flagged(df)` in a later stage if you want a strictly clean frame.

## Setup

```bash
pip install -r requirements.txt
```

## 1. Try it now with synthetic data

Before the real dataset package arrives, generate small synthetic stand-ins
(with a few deliberately bad records) to confirm the pipeline runs:

```bash
python tests/make_sample_raw_data.py --out-dir data/raw
python -m src.ingestion.run_ingestion --city Delhi
```

Then open `reports/data_quality_report.md`.

## 2. Run it on the real data

1. Drop the real extracts into `data/raw/`, matching the filenames in
   `src/ingestion/config.py` (or pass `--raw-dir` / edit the config to point
   elsewhere — column *names* inside each file don't need to match exactly,
   see the alias maps in `config.py`).
2. If SatPM arrives as a folder of monthly GeoTIFFs instead of one NetCDF file,
   just point `--raw-dir`'s `satpm` subfolder at it — `loaders.load_satpm()`
   handles both layouts automatically (folder must be named `satpm/`, or edit
   `config.SATPM_PATH`).
3. Run:

```bash
python -m src.ingestion.run_ingestion --raw-dir data/raw --city <YourCity>
```

## File overview

| File | Responsibility |
|---|---|
| `src/ingestion/config.py` | Paths, plausible value ranges, column-name aliases |
| `src/ingestion/loaders.py` | One loader per source, tolerant of naming/format variation |
| `src/ingestion/validators.py` | Schema/range/bbox/duplicate/completeness checks, per source |
| `src/ingestion/report.py` | Turns validation results into `data_quality_report.md` |
| `src/ingestion/run_ingestion.py` | CLI entry point tying it all together |
| `tests/make_sample_raw_data.py` | Synthetic data generator for testing before real data arrives |

## What each check catches

- **CPCB stations**: missing coordinates, coordinates outside India's bounding box,
  duplicate station IDs, duplicate lat/lon pairs (possible data-entry errors).
- **OpenAQ**: missing core fields, out-of-bbox coordinates, PM2.5 values outside
  0–1000 µg/m³, duplicate station/date/parameter rows, and per-station-month
  completeness (% of days with a reading) against a 50% threshold.
- **SatPM**: % of grid cells that are NaN or outside the plausible PM2.5 range,
  and the time range actually covered.
- **WorldPop**: % of cells that are nodata or outside a plausible per-pixel
  population range, plus the raster's total population sum as a sanity check
  against the city's known population.

## Next step (Stage 2)

Read `data/interim/*` and `reports/data_quality_report.md`, decide what to do
with flagged rows (keep with caution vs. `drop_flagged()`), then move on to
CRS harmonization, common-grid resampling, and the city/ward clip.

# Air Quality Sensor Audit — Population-Weighted PM2.5 Exposure Gap

**Problem:** Under India's National Clean Air Programme, cities receive funding based on
measured pollution reduction at their official monitoring stations — which means *where* a
city places its monitors can quietly influence its funding, independent of real air quality.

This project reconstructs population-weighted "true" exposure from satellite PM2.5 and
gridded population data, compares it against what the city's official monitoring network
reports, quantifies the gap, and recommends where the next monitor should go to close it.

**City:** Patna (see the reasoning for this choice in the project history / report).

## Architecture

Nine-layer pipeline: ingestion → spatial/temporal alignment → feature engineering →
bias-correction modeling → exposure & gap engine → sensor placement → serving artifacts →
API → dashboard. Full writeup with formulas, tools, and a build-order timeline:
[`docs/architecture.md`](docs/architecture.md).

## Progress

| Stage | Status | Docs |
|---|---|---|
| 1. Ingestion & Validation | ✅ | [`README_stage1.md`](README_stage1.md) |
| 2. Spatial & Temporal Alignment | ✅ | [`README_stage2.md`](README_stage2.md) |
| 3. Feature / Training Dataset | ✅ | [`README_stage3.md`](README_stage3.md) |
| 4. Bias-Correction Modeling | ⬜ | — |
| 5. Exposure & Gap Engine | ⬜ | — |
| 6. Sensor Placement | ⬜ | — |
| 7–9. Serving, API, Dashboard | ⬜ | — |

## Quickstart

```bash
pip install -r requirements.txt

# Try the full pipeline on synthetic data before using real extracts:
python tests/make_sample_raw_data.py --out-dir data/raw
python tests/make_sample_boundary.py --out data/raw/city_boundary.geojson
python -m src.ingestion.run_ingestion --city Patna
python -m src.alignment.run_alignment --resolution 100
python -m src.features.run_features
```

Each stage's README documents its own setup, real-data instructions, and (importantly) the
bugs that testing against synthetic data caught before they could hit real data.

## Repository layout

```
src/
  ingestion/   # Stage 1 — loaders, validators, data-quality report
  alignment/   # Stage 2 — CRS harmonization, common grid, clip, station-pixel join
  features/    # Stage 3 — feature engineering, spatial CV fold assignment
tests/         # Synthetic data generators for testing before real data arrives
docs/          # Architecture doc
reports/       # Sample outputs from a synthetic test run (committed as evidence)
data/          # raw/interim/processed — gitignored except for .gitkeep placeholders
```

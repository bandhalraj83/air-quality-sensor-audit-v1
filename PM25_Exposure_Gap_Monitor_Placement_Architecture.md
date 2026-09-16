PM2.5 Exposure Gap &
Monitor Placement System

Architecture & Technical Design Document

Decision-support architecture for population-weighted exposure, monitoring-network gap analysis, and sensor placement

## 1. Executive Summary

This document defines a production-oriented architecture for a PM2.5 Exposure Gap & Monitor Placement System. The system is deliberately designed as a decision-support pipeline rather than simply as a PM2.5 prediction model. Its central purpose is to quantify the difference between population-weighted exposure reconstructed from satellite data and the exposure represented by the existing CPCB monitoring network, localize that difference, and recommend locations for additional monitors that can reduce the population-weighted gap.

The design follows a layered architecture: Data Ingestion → Validation & Harmonization → Spatial/Temporal Alignment → Bias-Correction Modeling → Exposure & Gap Computation → Sensor Placement Optimization → API → Dashboard. The source design identifies three distinct quantities: true exposure, official exposure, and the gap between them. Keeping these concepts separate is the key architectural principle of the solution.

Source design explicitly defines the project as a decision-support pipeline and distinguishes the three quantities above.

## 2. Business / Policy Objective

The system should answer four practical questions for each selected city:

- What is the estimated population-weighted PM2.5 exposure across the city?
- What exposure does the existing CPCB monitor network imply when its readings are spatially interpolated?
- Where and by how much do those two views diverge, particularly in densely populated areas?
- Where should the next monitor be placed to produce the largest expected reduction in the population-weighted exposure gap?
## 3. Core Conceptual Model

## 4. High-Level Architecture

The following architecture is the recommended logical flow. Each layer has a single responsibility and produces artifacts consumed by the next layer.

DATA SOURCES
CPCB Stations | SatPM PM2.5 | WorldPop | OpenAQ
        │
        ▼
1. INGESTION & VALIDATION
Source loaders → schema checks → range/completeness checks
        │
        ▼
2. SPATIAL & TEMPORAL ALIGNMENT
CRS harmonization → common grid → city/ward clip → station-pixel join
        │
        ▼
3. FEATURE / TRAINING DATASET
Satellite PM2.5 + AOD/met covariates + station metadata → ground PM2.5 target
        │
        ▼
4. BIAS-CORRECTION MODELING
Ridge baseline ─┐
                ├→ Spatial CV → model selection → model artifact
Gradient Boost ─┘
        │
        ▼
5. EXPOSURE & GAP ENGINE
Calibrated city raster → True exposure
CPCB readings → IDW/Kriging → Official exposure
True vs Official → population-weighted gap surface
        │
        ▼
6. SENSOR PLACEMENT
Candidate sites → simulate monitor → re-interpolate → score gap reduction
        │
        ▼
7. PRECOMPUTED SERVING ARTIFACTS
GeoParquet / GeoJSON / GeoTIFF / model artifacts / placement results
        │
        ├──────────────► 8. FastAPI
        │                    │
        │                    ▼
        └──────────────► 9. Streamlit + Folium/pydeck Dashboard

## 5. Detailed Architecture by Layer

### 5.1 Data Layer

- CPCB station data provides existing monitoring locations and readings.
- SatPM provides satellite-derived PM2.5 and potentially AOD and meteorological covariates.
- WorldPop provides the population grid used for population weighting.
- OpenAQ provides ground-truth PM2.5 observations for calibration.
- Raw inputs remain untouched and read-only; processed outputs are stored separately.
### 5.2 Validation & Harmonization

- Validate schemas, units, coordinate ranges, dates, null rates, and plausible PM2.5 ranges.
- Standardize CRS and spatial metadata.
- Track source/date/version metadata so every derived artifact is reproducible.
- Preserve raw → interim → processed lineage.
### 5.3 Spatial & Temporal Alignment

- Use EPSG:4326 for interoperable storage where appropriate and a local UTM CRS for accurate distance/area calculations.
- The recommended 8-week approach is to aggregate the 100m WorldPop population to the coarser satellite grid.
- Clip data early to authoritative city/ward boundaries.
- Join each CPCB station to the corresponding satellite pixel using nearest-pixel or bilinear extraction.
- Aggregate OpenAQ observations to monthly values so they align with monthly satellite data.
- Apply a documented completeness threshold; the source suggests an example of at least 50% of days with valid readings per station-month.
### 5.4 Feature / Alignment Layer

- Build a station-month training table containing satellite PM2.5, optional AOD and meteorological variables, station metadata, temporal features, and ground PM2.5 target.
- Keep the training dataset auditable: every row should be traceable to a station, time period, source observation, and satellite pixel.
### 5.5 Modeling Layer

- Model 1: Linear/Ridge regression as an interpretable baseline.
- Model 2: XGBoost or LightGBM gradient boosting for nonlinear bias correction.
- Use spatial validation rather than random k-fold validation.
- Preferred validation: Leave-One-Station-Out; Leave-One-City-Out when sufficient cities are available.
- Report RMSE, MAE, R², and bias by concentration tercile.
- Select the model using spatial-CV performance while explicitly discussing the accuracy-versus-interpretability tradeoff.
### 5.6 Exposure & Gap Engine

- Apply the selected calibration model to every satellite pixel in the city.
- Calculate population-weighted true exposure.
- Interpolate CPCB readings using IDW; ordinary kriging is a stretch goal.
- Evaluate official exposure on exactly the same grid and with the same population weighting.
- Produce both a signed city-level gap and an absolute pixel/ward-level gap surface.
- The signed city-level gap is policy-relevant because it shows whether official monitoring understates or overstates reconstructed exposure.
### 5.7 Sensor Placement Layer

- Create candidate sites from grid-cell or ward centroids.
- Exclude candidates inside a configurable minimum distance from existing monitors.
- For each candidate, simulate adding a monitor using the calibrated value at that location.
- Re-run interpolation and calculate the resulting population-weighted gap reduction.
- Select the candidate with maximum reduction, then repeat for N sites.
- Return latitude, longitude, ward, estimated gap reduction, and population served.
### 5.8 Serving Layer

- FastAPI is a thin read layer over precomputed artifacts.
- Do not run raster inference or interpolation during API requests.
- Load artifacts once at startup and cache them in memory.
- Use Pydantic response schemas and return HTTP 404 for unknown cities.
### 5.9 Presentation Layer

- Streamlit + Folium/pydeck is the recommended default for an 8-week capstone.
- A React + Leaflet/Mapbox frontend is an optional portfolio-quality alternative.
- The dashboard should make the true-vs-official-vs-gap narrative immediately understandable.
## 6. Recommended Repository / Component Structure

pm25-exposure-gap/
├── data/
│   ├── raw/
│   │   ├── cpcb_stations.xlsx
│   │   ├── satpm_v6/
│   │   ├── worldpop_india_100m/
│   │   └── openaq_historical/
│   ├── interim/
│   └── processed/
│       ├── city_grids/
│       ├── station_training_table.parquet
│       └── city_boundaries/
├── src/
│   ├── ingestion/
│   ├── alignment/
│   ├── features/
│   ├── models/
│   ├── exposure/
│   ├── placement/
│   ├── api/
│   └── dashboard/
├── notebooks/
├── artifacts/
├── tests/
├── reports/
├── config/
│   └── cities.yaml
├── requirements.txt / pyproject.toml
└── README.md

## 7. Key Data Products / Artifacts

## 8. API Contract

## 9. Sensor Placement Algorithm

The recommended algorithm is a greedy maximum-coverage-style approach. It is computationally practical for the stated scope and produces an explainable ranking.

Input: current gap grid G, candidate sites C, desired monitors N

For iteration i = 1..N:
    For each candidate c in C:
        1. Add c with its calibrated PM2.5 value
        2. Re-run IDW/kriging
        3. Recompute population-weighted gap G'
        4. Score(c) = sum(G) - sum(G')
    Select c* with maximum score
    Add c* to selected sites
    Remove c* from candidate pool
    Update G

Output:
    ranked sites, coordinates, ward, estimated gap reduction,
    and population served.

## 10. Non-Functional Architecture Requirements

- Reproducibility: all transformations should be executable from configuration and source-version metadata.
- Auditability: retain intermediate datasets and model metrics rather than relying on notebook state.
- Performance: API requests should read precomputed artifacts instead of performing expensive geospatial calculations.
- Testability: ingestion, alignment, exposure, placement, API schemas, and model evaluation should be independently testable.
- Explainability: expose model metrics, calibration bias, interpolation method, and placement scoring logic.
- Configurability: city boundary, CRS, grid resolution, monitor exclusion radius, model choice, and placement N should be configuration-driven.
## 11. Validation & Quality Gates

## 12. Technology Stack

## 13. Eight-Week Delivery Plan

## 14. Risks and Mitigations

## 15. Recommended Dashboard Narrative

The dashboard should not feel like a generic geospatial visualization. The primary user journey should be: select a city → compare true and official exposure → locate the gap → inspect existing monitors → inspect recommended sites → understand why the recommended sites reduce the gap.

Example narrative: "Official monitoring estimates city-wide exposure at X μg/m³; satellite-based reconstruction estimates Y μg/m³ — a gap of Z μg/m³, concentrated in [ward names]."

## 16. Architecture Principles

- Decision-support first: the system exists to support monitoring and policy decisions, not merely prediction.
- Same grid, same population weights: true and official exposure must be directly comparable.
- Spatial validation over random validation: avoid leakage and overstated model performance.
- Precompute expensive geospatial operations: keep the API fast and simple.
- Explainability over unnecessary model complexity: a modest, defensible model is preferable to an opaque model that cannot be validated.
- Explicit uncertainty and limitations: policy recommendations should not be presented with false precision.
- Modular engineering: each stage should be independently testable and replaceable.
## 17. Source Design Coverage

This document reorganizes and expands the uploaded architecture/design into a formal technical document while preserving its core framing, layer boundaries, repository structure, modeling approach, exposure equations, greedy placement strategy, API endpoints, dashboard requirements, validation checkpoints, technology stack, 8-week plan, and project risks.


| Quantity | Definition | Role |
| --- | --- | --- |
| True exposure | Population-weighted PM2.5 reconstructed from calibrated satellite estimates and population grid. | Best city-wide proxy, including areas without monitors. |
| Official exposure | Exposure implied by existing CPCB readings after spatial interpolation on the same analysis grid. | Represents what the existing monitoring network effectively sees. |
| Exposure gap | Difference between calibrated satellite-derived exposure and monitor-derived exposure. | Localizes monitoring blind spots and drives placement recommendations. |


| Artifact | Format | Produced By | Consumed By |
| --- | --- | --- | --- |
| Station training table | Parquet | Alignment/features | ML training & evaluation |
| Calibrated PM2.5 city grid | GeoTIFF/Parquet | Model/exposure | Exposure, gap, dashboard |
| Official interpolated grid | GeoTIFF/Parquet | Exposure | Gap engine/dashboard |
| Ward gap summary | GeoJSON/Parquet | Exposure | API/dashboard |
| Trained calibration model | joblib/pickle | Modeling | Batch inference |
| Placement recommendations | GeoJSON/Parquet | Placement | API/dashboard |
| Model metrics & metadata | JSON/Parquet | Evaluation | Report/dashboard |


| Endpoint | Purpose | Primary Response |
| --- | --- | --- |
| /cities | List supported cities | City identifiers and metadata |
| /exposure/{city} | City-level exposure and ward breakdown | True exposure, official exposure, signed gap, ward results |
| /exposure/{city}/grid | Spatial exposure/gap data | GeoJSON FeatureCollection / tiles |
| /placement/{city}?n=5 | Recommended new monitor sites | Ranked sites + gap reduction |
| /monitors/{city} | Existing monitoring network | CPCB station locations + latest available readings |


| Gate | Check | Failure Impact |
| --- | --- | --- |
| Data | Schema, units, coordinate validity, nulls, dates | Invalid model inputs |
| Population | City totals against known Census/WorldPop totals | Incorrect population weighting |
| Temporal | Satellite and ground monthly alignment | Biased training pairs |
| Spatial | Station-to-pixel and CRS validation | Wrong calibration/exposure locations |
| Model | LOSO / city-held-out CV | Overoptimistic accuracy |
| Interpolation | IDW/kriging sensitivity to monitor geometry | Unstable official exposure |
| Uncertainty | Residual-based exposure uncertainty | Overconfident policy conclusions |
| Identification | Review satellite methodology for population-related dependencies | Potential policy bias |


| Layer | Recommended Technology |
| --- | --- |
| Geospatial I/O | rasterio, rioxarray, geopandas, xarray |
| Interpolation | scipy.spatial.cKDTree for IDW; pykrige for kriging |
| ML | scikit-learn, XGBoost or LightGBM |
| Spatial CV | GroupKFold/custom station or city grouping |
| API | FastAPI, Pydantic, Uvicorn |
| Dashboard | Streamlit + Folium/pydeck; React + Leaflet/Mapbox optional |
| Storage | Parquet, GeoTIFF, GeoJSON |
| Database | Not required at this project scale |


| Period | Deliverables |
| --- | --- |
| Weeks 1–2 | Data ingestion, validation, CRS/resolution alignment, city boundary processing, repository scaffolding. |
| Weeks 3–5 | Training table, Ridge baseline, gradient boosting, spatial CV, metrics, model selection. |
| Week 6 | Calibrated exposure, official exposure, gap surfaces, greedy sensor placement. |
| Week 7 | FastAPI, schemas, artifact loading/caching, endpoint testing. |
| Week 8 | Dashboard, report, visualizations, final validation and demo. |


| Risk | Why It Matters | Mitigation |
| --- | --- | --- |
| Data sparsity | Some cities may have only 2–4 CAAQMS stations. | Choose cities with adequate station counts; pool cities for calibration where justified; avoid overstating spatial certainty. |
| Resolution mismatch | Satellite grid is much coarser than WorldPop. | Aggregate population to satellite resolution for the primary 8-week implementation; document the tradeoff. |
| Spatial leakage | Random CV can inflate model performance. | Use LOSO or leave-one-city-out validation. |
| Interpolation instability | Few monitors can make official exposure sensitive to method and geometry. | Use IDW as baseline, test sensitivity, and treat kriging as a stretch goal. |
| Placement scope creep | Advanced facility-location optimization can consume project time. | Keep greedy placement as the core implementation. |
| Satellite product dependency | Source dates or methodology may not align with OpenAQ. | Verify temporal overlap and document product assumptions. |
| Policy overclaim | Satellite reconstruction is still a proxy, not direct individual exposure. | Report uncertainty and clearly label 'true exposure' as the project's best proxy. |

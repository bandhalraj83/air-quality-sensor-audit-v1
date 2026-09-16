# Stage 2 — Spatial & Temporal Alignment

Reads Stage 1's validated interim data, puts SatPM and WorldPop on one
common pixel grid in a local UTM projection, clips both to the city
boundary, samples both rasters at every CPCB station, aggregates OpenAQ to
monthly means, and joins everything into one station-month table — the
direct input to Stage 3's training dataset.

## You need a city boundary file first

The raw data package doesn't include one (see the architecture doc). Source
a polygon for your city from [GADM](https://gadm.org) or
[Bhuvan](https://bhuvan.nrsc.gov.in), save it as GeoJSON, and set
`--boundary path/to/file.geojson` (or edit `config.BOUNDARY_PATH`).

## Try it now with synthetic data

```bash
pip install -r requirements.txt
python tests/make_sample_raw_data.py --out-dir data/raw
python tests/make_sample_boundary.py --out data/raw/city_boundary.geojson
python -m src.ingestion.run_ingestion --city Patna
python -m src.alignment.run_alignment --resolution 100
```

Then check `reports/alignment_summary.md` and
`data/processed/aligned_station_months.parquet`.

## Run it on real data

```bash
python -m src.alignment.run_alignment --boundary data/raw/patna_boundary.geojson --resolution 100
```

## File overview

| File | Responsibility |
|---|---|
| `src/alignment/config.py` | Boundary path, analysis resolution, completeness threshold |
| `src/alignment/crs_utils.py` | Automatic UTM zone selection, raster reprojection |
| `src/alignment/boundary.py` | Load/validate the city boundary polygon |
| `src/alignment/grid.py` | Build the common grid; resample concentration vs. population fields differently |
| `src/alignment/clip.py` | Crop rasters to the city boundary |
| `src/alignment/station_join.py` | Sample raster values at station coordinates |
| `src/alignment/temporal.py` | Aggregate OpenAQ to monthly station means |
| `src/alignment/run_alignment.py` | CLI entry point tying it all together |
| `tests/make_sample_boundary.py` | Synthetic boundary polygon for testing |

## Design notes / things that bit us in testing (so they don't bite you)

- **Concentration vs. count fields are resampled differently.** PM2.5 is an
  intensive field (bilinear interpolation is fine). Population is an
  extensive field — summed, not averaged — so `resample_population_preserving_total()`
  rescales the resampled grid to match the *source raster's total over the
  same ground footprint* after reprojection. Comparing against the source
  raster's grand total instead (an earlier version of this bug) silently
  produces wrong numbers whenever the source raster (e.g. all of India)
  covers more area than the destination city grid — which is exactly the
  real-world case.
- **rioxarray needs spatial dims named `x`/`y` by default.** If your NetCDF
  uses `lat`/`lon` (common for gridded PM2.5 products), call
  `ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat")` before doing anything
  CRS-related, or it silently falls back to an identity transform and every
  reprojected value comes out NaN with no error raised.
- **Resolve duplicate station IDs before joining**, not after. Stage 1 flags
  them (`_flag_duplicate_station`); Stage 2 drops them prior to the
  station-metadata join so one physical station with two ID rows doesn't
  silently duplicate every row of its output.
- **CPCB `station_id` and OpenAQ `location_id` may not match on the real
  data** the way they do in the synthetic fixture. If the "rows with a
  matched ground-truth reading" line in the summary report comes out low,
  you'll likely need a coordinate-proximity join (nearest station within
  some distance threshold) instead of an exact-ID join — that's a
  reasonable thing to add here if it comes up.

## Next step (Stage 3)

Read `data/processed/aligned_station_months.parquet`, add any remaining
covariates (meteorology, land use, station metadata), and build the
training table: satellite PM2.5 + covariates as features, `ground_pm25` as
the label, split by station (not randomly) for spatial cross-validation.

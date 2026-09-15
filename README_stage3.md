# Stage 3 — Feature / Training Dataset

Reads Stage 2's `aligned_station_months.parquet`, filters to usable rows,
engineers features (month seasonality, distance to city center, station
type), assigns spatial cross-validation folds, and writes the table Stage 4
trains on.

## Run it

```bash
python -m src.features.run_features
```

Pass `--center-lat`/`--center-lon` (e.g. the city boundary's centroid) for a
more meaningful distance-to-center feature than the default station-mean
fallback. Pass `--meteorology path.csv` if you've added ERA5 or similar
covariates (see `engineer.merge_meteorology()` for the expected shape).

Then check `reports/training_table_summary.md` — read the filtering funnel
first. If most rows disappear at "missing satellite_pm25" or "missing
ground_pm25", that's telling you something about Stage 2's station-pixel
join or the CPCB/OpenAQ ID-matching problem flagged in Stage 2's README.

## Why leave-one-station-out shows up

With Patna's sparse CPCB network, `spatial_cv.py` will very likely pick
leave-one-station-out over k-fold (the threshold is
`config.MIN_STATIONS_FOR_KFOLD = 15`). That's intentional, not a bug to
"fix" by lowering the threshold — k-fold metrics from a handful of groups
are unstable and will overstate how well Stage 4's model generalizes.
Report Stage 4's per-fold metrics individually, not just the mean.

## File overview

| File | Responsibility |
|---|---|
| `src/features/config.py` | Filtering rules, feature list, CV settings |
| `src/features/engineer.py` | Month cyclical encoding, distance-to-center, imputation, one-hot encoding, optional meteorology merge |
| `src/features/spatial_cv.py` | Group-based fold assignment (k-fold or leave-one-station-out) |
| `src/features/run_features.py` | CLI entry point |

## A bug this caught, for your methodology section

Station type came out entirely missing from Stage 2's output the first time
this ran — traced back to Stage 1's column-alias list expecting
`station_type` or `site type`, but the actual CPCB column being `Station
Type` (with a space). `_resolve_columns` matches on the lowercased column
name, and `"station type"` simply wasn't in the alias list. Nothing errored
— the column was just silently dropped. Worth deliberately checking Stage
1's data-quality report against the raw file's actual column headers once
you have the real CPCB extract, rather than assuming the aliases cover it.

## Next step (Stage 4)

Read `data/processed/training_table.parquet`. Train Ridge and a gradient
boosting model, evaluating with the `cv_fold` column already assigned here
(don't re-split) — that keeps Stage 3 as the single source of truth for
what counts as train vs. test for any given station.

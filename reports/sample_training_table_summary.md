# Stage 3 -- Training Table Summary

## Filtering funnel

| Step | Rows remaining |
|---|---:|
| aligned station-months (Stage 2 output) | 22 |
| after requiring reliable monthly completeness | 20 |
| after dropping missing satellite_pm25 | 12 |
| after dropping missing ground_pm25 | 12 |

## Spatial cross-validation

Strategy used: **leave-one-station-out (6 stations -> 6 folds)**

|   cv_fold |   n_rows |   n_stations |
|----------:|---------:|-------------:|
|         0 |        2 |            1 |
|         1 |        2 |            1 |
|         2 |        2 |            1 |
|         3 |        2 |            1 |
|         4 |        2 |            1 |
|         5 |        2 |            1 |

## Target (`ground_pm25`) distribution

| Stat | Value |
|---|---:|
| count | 12.00 |
| mean | 99.97 |
| std | 37.44 |
| min | 64.23 |
| 25% | 71.34 |
| 50% | 82.67 |
| 75% | 146.76 |
| max | 155.24 |

## Features included (8)

- `satellite_pm25`
- `population_at_station`
- `distance_to_city_center_km`
- `month_sin`
- `month_cos`
- `station_type_Industrial`
- `station_type_Residential`
- `station_type_Traffic`

## Final table

- 12 rows, 6 distinct stations -> `training_table.parquet`

**Caution:** fewer than 8 distinct stations remain. Spatial CV metrics from this few groups will be noisy -- report per-fold results individually in Stage 4, not just the mean, and treat model comparisons as indicative rather than conclusive.

# Stage 1 -- Data Quality Report

Generated: 2026-09-15 19:05
City: **Patna**

This report covers all four raw sources after ingestion. Flagged records are **retained** in the interim data with boolean `_flag_*` columns (tabular sources) or masked to NaN (raster sources) -- nothing is silently dropped at this stage. Stage 2/3 decide what to do with flagged records.

## Summary

| Source | Type | Records / Cells | Key concern |
|---|---|---:|---|
| CPCB | tabular | 13 | _flag_out_of_bbox (2) |
| OpenAQ | tabular | 565 | _flag_out_of_bbox (50) |
| SatPM | raster | 800 | n_out_of_range (1) |
| WorldPop | raster | 40,000 | n_out_of_range (1) |

## CPCB

- Records in: **13**
- Records out (all retained, flagged not dropped): **13**

| Check | Flagged count | % of records |
|---|---:|---:|
| `_flag_missing_coords` | 1 | 7.7% |
| `_flag_out_of_bbox` | 2 | 15.4% |
| `_flag_duplicate_station` | 1 | 7.7% |
| `_flag_duplicate_location` | 1 | 7.7% |

**Notes:**
- Some stations share identical coordinates -- check whether these are genuinely co-located instruments or a lat/lon entry error.

## OpenAQ

- Records in: **565**
- Records out (all retained, flagged not dropped): **565**

| Check | Flagged count | % of records |
|---|---:|---:|
| `_flag_missing_core` | 1 | 0.2% |
| `_flag_out_of_bbox` | 50 | 8.8% |
| `_flag_out_of_range` | 4 | 0.7% |
| `_flag_duplicate` | 41 | 7.3% |
| `station_months_below_completeness_threshold` | 0 | 0.0% |

**Notes:**
- 0 of 22 station-months fall below the 50% daily-completeness threshold (kept, but Stage 3 should treat them cautiously or exclude them).

## SatPM

- Grid shape: **(2, 20, 20)**

| Check | Value |
|---|---:|
| `n_nan` | 0 |
| `pct_nan` | 0.0 |
| `n_out_of_range` | 1 |
| `pct_out_of_range` | 0.125 |

| Stat | Value |
|---|---:|
| `min` | 70.05 |
| `max` | 149.91 |
| `mean` | 110.50 |

**Notes:**
- Time coverage: 2024-01-01 to 2024-02-01 (2 months).

## WorldPop

- Grid shape: **(200, 200)**

| Check | Value |
|---|---:|
| `n_nodata` | 0 |
| `pct_nodata` | 0.0 |
| `n_out_of_range` | 1 |
| `pct_out_of_range` | 0.003 |

| Stat | Value |
|---|---:|
| `min` | 0.05 |
| `max` | 225.19 |
| `total_population_sum` | 1,202,312.50 |

**Notes:**
- Sum of all valid pixel values ~= total population represented in this raster (1,202,312); sanity-check this against the city's known population.

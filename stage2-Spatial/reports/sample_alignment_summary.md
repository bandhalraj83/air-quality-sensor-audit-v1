# Stage 2 -- Alignment Summary

- Target CRS: `EPSG:32643` (auto-selected UTM zone)
- Common grid: 330 x 387 px @ 100.0 m
- SatPM aligned grid: (2, 377, 330) (time, H, W)
- WorldPop aligned grid: (377, 330)
- Population sum before clip: 1,202,312; after clip (city extent only): 568,239
- CPCB stations with usable coordinates: 11
- Of those, outside the clipped city extent (no pixel match): 5
- OpenAQ station-months: 20 (20 reliable, completeness >= 50%)
- Final aligned station-month table: 22 rows -> `aligned_station_months.parquet`
- Rows with a matched ground-truth reading: 20 / 22

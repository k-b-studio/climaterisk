# HII 6-Month Drought Forecast — Map

Maps the latest HII drought forecast onto Thailand tambon polygons. Same
workflow as `flood_forecast_accuracy/03_map_forecast.py`, adapted to the
drought product.

## Data

- Forecast: `IECC/DroughtRiskArea_HII/202606droughtForecast_6month.xlsx`
  (forecast *issued* Jun 2026, covering Jun–Nov 2026, lead 0–5, 7,387 tambons).
- Geometry: `IECC/TH_TAMBON_json/tha_admbnda_adm3_rtsd_20220121_geo.json`.
- Join: forecast `TAMBON_IDN` == geojson `ADM3_PCODE` without the `TH` prefix
  (7,381 / 7,425 polygons matched).

Unlike the 3-class flood product, drought has **2 classes**:

| TYPE_E | TYPE_T | colour |
|---|---|---|
| `norisk` | ไม่เสี่ยง | grey `#D5D5D5` |
| `drought` | เสี่ยงแล้ง | brown-amber `#C77B2B` |

## Run

```
python3 01_map_forecast.py
```

## Outputs

- `figures/map/map_YYYYMM_leadN.png` — one choropleth per forecast month
  (Jun–Nov 2026), each with legend and tambon-count box.
- `figures/map/map_panel_6month.png` — combined 2×3 panel.
- `output/map/drought_forecast_map_202606.html` — interactive folium map with a
  layer toggle for each of the 6 forecast months, hover tooltips
  (tambon / district / province / drought class) and a legend.

The HTML legend is generated from the `COLORS`/`LABELS` dicts, so swatches
always match the map — change the palette in one place at the top of the script.

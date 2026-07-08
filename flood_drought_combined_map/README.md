# HII 6-Month Flood + Drought Combined Map

Merges the latest HII **flood** and **drought** 6-month forecasts (both issued
Jun 2026) into a single tambon map. Same workflow as the flood / drought map
scripts.

## Data

- Flood:   `IECC/Flood Forecast 6 month/202606FloodForecast_6month.xlsx`
- Drought: `IECC/DroughtRiskArea_HII/202606droughtForecast_6month.xlsx`
- Geometry:`IECC/TH_TAMBON_json/tha_admbnda_adm3_rtsd_20220121_geo.json`
- Both forecasts cover Jun–Nov 2026 (lead 0–5), joined on
  `TAMBON_IDN` == geojson `ADM3_PCODE` minus the `TH` prefix.

## Combined classification

Each tambon-month has a flood class and a drought class; they are merged into
one category, overlaps first:

| Combined class | Rule | Colour |
|---|---|---|
| No risk | neither | grey `#D5D5D5` |
| Flood | flood risk only | blue `#3964E4` |
| Flash flood | flashflood only | red `#E0402F` |
| Drought | drought only | amber-brown `#C77B2B` |
| Flood + Drought | flood risk **and** drought | green `#2E8B57` |
| Flash flood + Drought | flashflood **and** drought | brown `#6B4226` |

> **Note for the Jun 2026 vintage:** flood and drought are entirely mutually
> exclusive in all 6 forecast months — there are **no overlap tambons**, so the
> green / brown categories appear in the legend but not on the map. The overlap
> logic is generic and will colour those areas automatically for any future
> forecast that does contain overlaps.

## Run

```
python3 01_map_combined.py
```

## Outputs

- `figures/map/map_YYYYMM_leadN.png` — per-month choropleth (Jun–Nov 2026)
- `figures/map/map_panel_6month.png` — combined 2×3 panel
- `figures/map/map_6month_blend.png` — all 6 months merged into one map. Each
  tambon's colour is the **blend (mean) of its 6 monthly class colours**, so
  stronger colour = at risk in more months (persistent / consecutive risk),
  greyer = at risk in fewer months, and a mixed hue = different hazards in
  different months. Note: a colour average reflects *how many* risk months, not
  whether they are strictly consecutive.
- `output/map/flood_drought_map_202606.html` — interactive folium map, 6
  toggleable monthly layers, hover tooltips, legend.

Legend swatches are generated from the `COLORS`/`LABELS` dicts, so they always
match the map — edit the palette in one place at the top of the script.

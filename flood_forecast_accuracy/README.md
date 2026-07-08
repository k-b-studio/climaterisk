# HII 6-Month Flood Forecast — Accuracy / Verification

Evaluates how accurate HII's monthly 6-month flood forecasts have been, by
comparing each **reporting month** against the forecasts that were issued for
that same month in the preceding 1–5 months.

## Data

Source: `IECC/Flood Forecast 6 month/YYYYMMFloodForecast_6month.xlsx`
(30 monthly files, Jan 2024 → Jun 2026). Each file is the forecast *issued*
in month `YYYYMM` and predicts a flood class for that month and the next five:

| class | TYPE_E | meaning |
|---|---|---|
| 0 | `norisk` | no flood expected |
| 1 | `flood risk` | flooding |
| 2 | `flashflood` | flash flooding |

Coverage is complete and uniform: **7,387 tambons × 6 lead times** in every file.

## Method (categorical forecast verification)

For each target month **T**:

- **Truth** = the assessment made *in* month T (lead-0) — the "reporting month".
- **Forecasts scored** = what was issued 1–5 months earlier (lead 1–5).

Because floods are rare (**8.6 %** base rate of tambon-months), raw accuracy
(~94–95 %) is misleading — it just rewards calling `norisk`. We instead use the
standard rare-event skill scores on the binary event *flood = flood risk OR
flashflood*:

- **POD** (detection rate) = H / (H+M)
- **FAR / Success ratio** = false alarms / forecast-floods
- **CSI** (critical success index) — headline skill, H / (H+M+F)
- **BIAS** = forecast / observed flood frequency (1 = unbiased)
- **HSS** (Heidke skill score) vs random

Scoring window: **target months 2025-06 → 2026-06** (13 months), per request.

> Caveat: lead-0 is HII's own in-month assessment, not independent gauge
> observation. These metrics therefore measure *forecast consistency* — how well
> earlier forecasts matched the final reported picture — not validation against
> ground-truth inundation.

## Key findings

1. **Skill is moderate and degrades gracefully with lead time.** CSI falls from
   **0.49 (1 month ahead)** to **0.43 (5 months ahead)**; HSS 0.63 → 0.57.
   Detection (POD) ~0.57 → 0.52, success ratio ~0.77 → 0.70. The forecast
   horizon adds surprisingly little error — most skill is set by month 1.

2. **The system under-warns.** Frequency bias is **~0.70–0.75 at every lead** —
   earlier forecasts consistently flag *fewer* flood tambons than the reporting
   month ends up showing. ~40–45 % of reported floods were not flagged a month
   earlier (misses), and that rises with lead time.

3. **The 2025 monsoon peak was the hardest.** Oct 2025 reported ~2,800 flooded
   tambons but was forecast at only ~1,400–1,550 (≈ half) at all leads — the
   magnitude of the peak month was systematically under-predicted (see F4).

4. **The challenge is *occurrence*, not *severity*.** Within any target month the
   forecast never confuses flood risk ↔ flashflood (off-diagonals = 0.00); all
   errors are flood ↔ norisk. Flash floods are missed slightly more often
   (~50–55 % miss) than ordinary flood risk (~40–45 % miss).

5. **Strong regional contrast.** Skill is good in **Central / Southeast**
   (CSI ~0.62–0.66) but poor in the **Southwest** (~0.13) and **Northeast**
   (~0.33) — these regions need the most forecast caution.

6. **Seasonality dominates.** Wet-season target months score well (Sep 2025 CSI
   0.76, Dec 2025 0.74); dry-season months (Jan–Apr 2026) have so few events that
   their CSI is statistically noisy (a handful of calls swing it between ~0 and
   1.0), so interpret those cells via event counts in F4, not CSI alone.

## Files

Run order:
```
python3 01_build_panel.py       # assemble 30 files -> data/*.csv
python3 02_verify_accuracy.py   # accuracy metrics + figures
python3 03_map_forecast.py      # map latest forecast (PNG + interactive HTML)
```

## Map of the latest forecast (`03_map_forecast.py`)

Maps the most recent forecast (issued **Jun 2026**) onto Thailand tambon
polygons (`TH_TAMBON_json`, joined via `ADM3_PCODE` = `TH`+`TAMBON_IDN`,
7,381 / 7,387 tambons matched). Colours: **No risk = yellow, Flood risk =
orange, Flash flood = red**, grey = no data.

- `figures/map/map_YYYYMM_leadN.png` — one choropleth per forecast month
- `figures/map/map_panel_6month.png` — combined 2×3 panel (Jun–Nov 2026)
- `output/map/flood_forecast_map_202606.html` — interactive folium map with a
  layer toggle for each of the 6 forecast months, hover tooltips
  (tambon / district / province / forecast) and a legend.

**Figures** (`figures/`)
- `F1_skill_vs_leadtime.png` — headline skill & bias vs lead time
- `F2_csi_heatmap.png` — CSI by target month × lead
- `F3_confusion_by_lead.png` — 3-class confusion matrices per lead
- `F4_warned_counts_timeseries.png` — reported vs forecast flood extent
- `F5_region_csi_heatmap.png` — skill by region × lead
- `F6_severity_detection.png` — detection rate by severity & lead

**Tables** (`output/`)
- `S1_metrics_by_lead.csv` — pooled skill scores per lead (headline)
- `S2_metrics_by_target_lead.csv` — per target month × lead
- `S3_confusion_by_lead.csv` — 3-class contingency counts
- `S4_region_by_lead.csv` — region × lead skill
- `S5_severity_detection.csv` — recall by observed severity
- `S6_warned_counts.csv` — reported vs forecast warned-tambon counts

# Code Structure — `rain_flood_forecast_analysis/`

## Pipeline position

```
IECC/Rain Forecast 6 month/*.csv            (province × month rainfall, 2024-26)
IECC/Flood Forecast 6 month/*.xlsx          (tambon × month flood class, 30 files)
flood_exposure_analysis/data/province_year.csv  (actuals 2019-2025)
        │
        ▼
01_clean_prepare.py ─────► data/rain_province_month.csv
                           data/flood_forecast_province_month.csv
                           data/province_meta.csv
                           data/historical_province_year.csv
        │
        ├──► 02_analyze_visualize.py  → output/ (12 CSV) + figures/ (F1–F7)
        │
        └──► 03_portfolio_forward.py  → output/ (4 CSV) + figures/ (P1–P2)
```

## How to run

```bash
python3 01_clean_prepare.py        # ~40s (reads 30 Excel forecast files)
python3 02_analyze_visualize.py    # ~5s
python3 03_portfolio_forward.py    # ~3s  (depends on 02's forward_risk_scores_2026.csv)
```

Dependencies: `numpy`, `pandas`, `matplotlib`, `scipy`. Thai font `Thonburi`.

> **Note (OneDrive):** if a run dies with `TimeoutError: [Errno 60]`, an output
> file is a cloud-only placeholder that failed to hydrate. Delete the stale
> files in `output/`/`figures/` (scripts regenerate them) or mark the folder
> "Always keep on this device".

---

## `01_clean_prepare.py` — cleaning & harmonization

| Section | What it does | Key objects |
|---|---|---|
| 0 Paths & constants | IECC paths, region map (code→TH/EN), season & quarter maps | `REGION_MAP`, `SEASON_BY_MONTH`, `QUARTER_BY_MONTH` |
| 1 Cleaning helpers | `norm_province` (strip `จ.`, unify Bangkok), `add_calendar_keys` | — |
| 2 Province metadata | Canonical code↔name↔region dictionary from latest flood file | `province_meta.csv` |
| 3 Rain forecast | Unify `Rainfall`/`Rainfall.mm.` column + names; **consensus = mean across issuances** per (province, forecast month) | `rain_province_month.csv` |
| 4 Flood forecast | 30 monthly files → keep **most recent issuance** per target month → province at-risk **share** of tambons by type | `flood_forecast_province_month.csv` |
| 5 Historical | Reuse sibling cleaned actuals, attach code/region | `historical_province_year.csv` |
| 6 Run & write | Write 4 tables + console season/year summary | — |

**Cleaning performed:** column-name drift across years, `จ.` prefix, Bangkok
spellings, numeric coercion, multi-issuance de-duplication (latest lead wins),
tambon→province aggregation to a bounded [0,1] share.

---

## `02_analyze_visualize.py` — validation, score, breakdowns

| Section | What it does | Outputs |
|---|---|---|
| 0 Setup | Load 4 clean tables; `MONSOON=(6,10)` | — |
| 1 FACTORS | Documents the inputs (flood + history in the score; rain for timing only); `WEIGHTS` (one place to change) | — |
| 2 Signal builders | `forecast_signals(year)`, `historical_vulnerability(upto_year)` — reused for validation **and** scoring | — |
| **3 Validation** | Spearman of each factor vs actual damage (2024, 2025); standardized factor regression; **out-of-time composite test** | `S1_forecast_validation.csv`, `S2_factor_regression.csv`, `S3_composite_validation.csv` |
| 4 Risk-level meaning | 5-level interpretation table | `risk_level_meaning.csv` |
| 5 Forward score | 2026 composite, rescale 0-100, quintile 5-level class | `forward_risk_scores_2026.csv`, `top20_forward_risk_2026.csv` |
| 6 Breakdowns | National monthly profile; quarterly; seasonal; region (area); type-of-risk by region | `national_monthly_profile.csv`, `quarterly_2026.csv`, `seasonal_2026.csv`, `region_summary_2026.csv`, `type_of_risk_by_region.csv` |
| 7 Correlation | Spearman matrix: factors ↔ vulnerability ↔ actuals | `correlation_matrix.csv` |
| 8 Figures | F1–F7 (see below) | `figures/*.png` |
| 9 Console summary | Prints every headline stat in `EXPLANATION.md` | stdout |

### Figures

| File | Shows |
|---|---|
| `F1_top20_forward_risk_2026.png` | Top-20 provinces by 2026 forward score, colored by level |
| `F2_forecast_validation.png` | Forecast rain & flood-share vs actual 2025 housing damage (Spearman annotated) |
| `F3_monthly_seasonal_profile.png` | National monthly rainfall + at-risk share, monsoon shaded (2024/25/26) |
| `F4_quarterly_2026.png` | Q1–Q4 2026 rainfall vs flood at-risk share |
| `F5_region_type_breakdown.png` | Risk by region + flood-vs-flashflood share by region |
| `F6_correlation_matrix.png` | Spearman heatmap of all factors and actuals |
| `F7_risk_levels_all_provinces.png` | Level distribution + all 77 provinces ranked |

---

## `03_portfolio_forward.py` — portfolio impact

| Section | What it does | Outputs |
|---|---|---|
| 1 PORTFOLIOS | Per-portfolio damage-dimension weights (Mortgage / SME / Auto) | — |
| 2 Vulnerability | Portfolio-specific historical composite (cumulative 2019-2025) | — |
| 3 Scores | `0.50 flood + 0.50 portfolio-history`; 5-level class | `portfolio_forward_scores_2026.csv`, `top20_by_portfolio_2026.csv` |
| 4 Region exposure | Mean score per region × portfolio | `portfolio_region_exposure_2026.csv` |
| 5 Figures | P1 three top-20 panels; P2 region×portfolio heatmap | `figures/P1*, P2*` |

---

## Design decisions worth knowing before editing

1. **Weights live in one dict (`WEIGHTS`)** in `02`; `03` imports the same split
   and only re-weights the history component per portfolio.
2. **Forecast "consensus"** averages all monthly issuances for a target month
   (rain) / **keeps the latest issuance** (flood) — flood is categorical so the
   shortest-lead run is the best single estimate; rain is continuous so the mean
   is a sensible smoother.
3. **Monsoon window (Jun-Oct)** is the scoring window because that is when 2026
   flood risk and rainfall both peak (`quarterly_2026.csv`, Q3 highest).
4. **Rainfall is excluded from the score on purpose** — validation shows raw
   monsoon volume is *negatively* correlated with damage across provinces
   (drainage/exposure confounding); dropping it raised the out-of-time housing
   validation from ρ = 0.29 to 0.39. It is kept for the seasonal/timing layer
   only. Do **not** add it back to the score without re-reading
   `S1_forecast_validation.csv` and `S3_composite_validation.csv`.
5. **Quintiles cut on ranks** (tie-safe), same convention as the sibling project.
6. **Same signal builders feed validation and scoring**, so the formula tested
   out-of-time in `S3` is exactly the formula applied to 2026.

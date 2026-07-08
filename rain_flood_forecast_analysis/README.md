# Rain + Flood Forecast Integration — Forward-Looking Flood Risk (2026)

A forward-looking flood-risk classification of Thailand's 77 provinces for the
**2026 six-month horizon**, built by integrating three sources and *validating*
the forecasts against historical actuals before using them.

## What is new vs `flood_exposure_analysis/`

| | `flood_exposure_analysis/` (sibling) | `rain_flood_forecast_analysis/` (this) |
|---|---|---|
| Direction | Backward — historical exposure 2019-2025 | **Forward — 2026 forecast horizon** |
| Sources | DDPM historical damage only | **+ Rain Forecast 6m + Flood Forecast 6m** |
| Core question | Who *was* exposed? | **Who *will be* at risk in 2026, and when?** |
| New dimensions | — | **Quarterly / seasonal / type-of-risk** (from monthly forecasts) |

## The three data sources (`IECC/`)

1. **Rain Forecast 6 month** — province × month forecast rainfall (mm), 2024-2026.
2. **Flood Forecast 6 month** — subdistrict × month categorical flood-risk
   (`norisk` / `flood risk` / `flashflood`), 6 months ahead.
3. **Flood Historical Data** — actual province × year damage 2019-2025
   (reused from the sibling project's cleaned `province_year.csv`).

All three join on the standard Thai province code (77/77 provinces match).

## Pipeline

```
01_clean_prepare.py     -> data/   (4 clean tables; ~40s, reads 30 forecast files)
02_analyze_visualize.py -> output/ + figures/   (validation, score, breakdowns)
03_portfolio_forward.py -> output/ + figures/   (Mortgage / SME / Automobile)
```

```bash
python3 01_clean_prepare.py
python3 02_analyze_visualize.py
python3 03_portfolio_forward.py
```

Dependencies: `numpy`, `pandas`, `matplotlib`, `scipy`. Thai font `Thonburi`
(macOS built-in) for province labels.

## The score (one line)

```
risk_score = 0.50·FloodForecast + 0.50·HistoricalVulnerability
```

evaluated on the **monsoon window (Jun-Oct)**, rescaled 0-100, and cut into
5 risk levels. Only the two factors that **validate positively** against actual
damage are in the score; **rainfall is deliberately excluded** (geographically
confounded — see below) and is used for the *seasonal/timing* layer instead.
Weights are set by the **validation** (`02` SECTION 3), not by taste — see
`EXPLANATION.md`.

## Key documents

- `EXPLANATION.md` — what the analysis proves, the honest rainfall finding, and
  the credit-risk meaning.
- `CODE_STRUCTURE.md` — section-by-section map of the three scripts and every
  output file.

## Headline results

- **History is the strongest damage predictor** (Spearman ρ ≈ 0.70-0.75 vs 2025
  actuals); the **flood-forecast share adds a positive forward signal on housing
  / collateral damage**; **raw monsoon rainfall is geographically confounded**
  (the wettest provinces drain to the sea — ρ is *negative*, −0.43 vs housing),
  so it is **excluded from the cross-province score** and used only for the
  *seasonal / temporal* view. Dropping rain raised the score's out-of-time
  validation on housing from ρ = 0.29 to **0.39** (p = 0.0006).
- **2026 risk peaks in Q3 (Jul-Sep)**: flood at-risk share rises from ~0.4% in
  Q1 to **12.7% in Q3**; the single peak month is **September**.
- **Type of risk splits by geography:** the **Northeast and Central** plains are
  **riverine-flood** dominated; the **North** is **flashflood** dominated
  (mountainous terrain).
- The **North** is the most flood-exposed region for all three portfolios.

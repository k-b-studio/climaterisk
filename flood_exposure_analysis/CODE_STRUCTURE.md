# Code Structure: `03_credit_climate_risk.py`

## Pipeline position

```
gd027_flood_stat2562…2568_final.xlsx  (DDPM raw, BE 2562–2568 = 2019–2025)
        │
        ▼
01_clean_prepare.py ──────► data/province_year.csv   (493 rows, 77 provinces × 7 years)
                            data/district_year.csv   (3,212 rows, 2020–2024)
        │
        ├──► 02_analyze_visualize.py     (original: humanitarian composite, kept unchanged)
        │
        └──► 03_credit_climate_risk.py   (NEW: credit-risk overlay + statistical evidence pack)
                    │
                    ├── output/credit/   (10 CSV files)
                    └── figures/credit/  (6 PNG figures)
```

## How to run

```bash
python3 01_clean_prepare.py        # only if data/ not yet built
python3 03_credit_climate_risk.py  # ~5 seconds
```

Dependencies: `numpy`, `pandas`, `matplotlib`, `scipy` (≥1.9 for `binomtest`),
`scikit-learn`. Thai font `Thonburi` (macOS built-in) for province labels.
All randomness comes from a single seeded generator (`default_rng(42)`, used
once for the S6 simulation); the C5 figure re-uses the stored S6 draws, so
every number — in CSVs and figures — is exactly reproducible and mutually
consistent.

> **Note (OneDrive):** if a run dies with `TimeoutError: [Errno 60]` on an
> output CSV, the existing file is a cloud-only OneDrive placeholder that
> failed to hydrate. Delete the stale files in `output/credit/` and
> `figures/credit/` (the script regenerates all of them) or mark the project
> folder "Always keep on this device".

## Section map

| Section | Lines (approx.) | What it does | Key objects |
|---|---|---|---|
| Setup & load | 17–45 | Paths, font, load `province_year.csv`; defines the 12 scoring dimensions `DIMS` (extent counts and THB excluded — see ADJUSTMENT.md §1.6) | `pv`, `DIMS`, `DIM_LABELS` |
| Aggregation & normalization | 47–66 | Province cumulative totals 2019–2025; `years_affected` → frequency; `norm()` = log1p → min-max to [0,1]; normalized matrix | `agg`, `freq`, `norm()`, `nrm` |
| **S1** Correlation structure | 68–73 | Spearman matrix of the 12 dimensions (justifies component groupings) | `corr` → `S1_dimension_spearman_corr.csv` |
| **S2** PCA benchmark | 75–93 | 3-component PCA on `nrm`; PC1 oriented so higher = more exposed (the saved loadings are sign-flipped together with `pc1`, so CSV and validation always agree) | `pc1`, `pc1_var` → `S2_pca_loadings.csv` |
| Portfolio definitions | 95–130 | `PORTFOLIOS` dict: per portfolio, 5 components → (columns, weight). The single place to change weights. `"FREQ"` sentinel maps a component to the frequency series | `PORTFOLIOS` |
| Score construction | 133–158 | `build_score()`: per component, mean of normalized columns (or freq) × weight; rescale to 0–100; 5-level quintile classification on **ranks** (tie-safe) | `scores`, `risk` → `credit_portfolio_scores.csv` |
| S2 validation | 160–170 | Spearman of each portfolio score vs PC1 + top-20 overlap | → `S2_pca_validation.csv` |
| **S3** Trend tests | 172–194 | Per dimension on national yearly totals: Mann-Kendall (Kendall τ vs time), Theil-Sen slope, OLS slope/R²/p | `trend` → `S3_trend_tests.csv` |
| **S4** Persistence | 196–226 | For affected_people / households / housing: (a) Spearman ρ for each consecutive year-pair; (b) top-quintile retention pooled over 6 pairs (96 trials) vs 20% base rate, exact binomial test | `persist`, `retention` → `S4_persistence_*.csv` |
| **S5** Concentration | 228–250 | `gini()` (exact formula on sorted values); top-10/top-20 province shares for 4 dimensions | `conc` → `S5_concentration.csv` |
| **S6** Weight sensitivity | 252–283 | 2,000 draws/portfolio: each weight × U(0.5, 1.5), renormalized to sum 1, score rebuilt from stored component matrix (`all_comps`), top-20 overlap + rank Spearman vs baseline. Overlap arrays are kept in `sens_overlaps` and re-used by figure C5 | `sens`, `sens_overlaps` → `S6_weight_sensitivity.csv` |
| Projections | 285–308 | 2026–2028 for the 4 credit-relevant dimensions; OLS point + ±1 SE residual band, Theil-Sen as robust cross-check; clipped at 0 | `proj` → `credit_projection_2026_2028.csv` |
| Figures C1–C6 | 311–446 | See figure table below | `figures/credit/*.png` |
| Console summary | 448–467 | Prints every statistic used in EXPLANATION.md | stdout |

## Output files (`output/credit/`)

| File | Content | Used in EXPLANATION.md |
|---|---|---|
| `credit_portfolio_scores.csv` | 77 provinces × {mortgage, business_sme, automobile} score (0–100) + 5-level class + raw context columns | §2 top-10 lists |
| `S1_dimension_spearman_corr.csv` | 12×12 Spearman matrix | grouping rationale |
| `S2_pca_loadings.csv` | PC1–PC3 loadings per dimension | Claim 4 |
| `S2_pca_validation.csv` | ρ vs PC1, p-values, top-20 overlap per portfolio | Claim 4 |
| `S3_trend_tests.csv` | τ, MK p, Theil-Sen slope, OLS slope/R²/p, slope as % of mean — all 12 dimensions | Claim 1 |
| `S4_persistence_by_yearpair.csv` | Spearman ρ per consecutive year-pair per dimension | Claim 2 |
| `S4_persistence_summary.csv` | Mean lag-1 ρ, top-quintile retention, binomial p | Claim 2 |
| `S5_concentration.csv` | Gini, top-10/20 shares per dimension | Claim 3 |
| `S6_weight_sensitivity.csv` | Mean/p5/min top-20 overlap, rank ρ per portfolio | Claim 4 |
| `credit_projection_2026_2028.csv` | OLS + Theil-Sen projections with ±1 SE band | Claim 5 |

## Figures (`figures/credit/`)

| Figure | Shows | Supports |
|---|---|---|
| `C1_top20_by_portfolio.png` | Three top-20 bar panels (mortgage / SME / auto), colored by 5-level risk class | Where to apply limits & pricing |
| `C2_lorenz_concentration.png` | Lorenz curves + Gini for 4 dimensions | Claim 3 |
| `C3_credit_trends_projection.png` | 2×2 trend panels with OLS + Theil-Sen + MK p-values annotated, projection to 2028 with ±1 SE band | Claims 1, 5 |
| `C4_persistence.png` | Left: lag-1 Spearman per year-pair; right: top-quintile retention vs 20% base rate (the p-value in the caption is computed from `retention`, not hardcoded) | Claim 2 |
| `C5_weight_sensitivity.png` | Histograms of top-20 overlap under ±50% weight perturbation — plots the exact draws behind `S6_weight_sensitivity.csv` | Claim 4 |
| `C6_dimension_correlation.png` | Annotated 12×12 Spearman heatmap | Grouping rationale |

## Design decisions worth knowing before editing

1. **Weights live in one dict (`PORTFOLIOS`).** Changing a weight automatically
   propagates to scores, classifications, sensitivity analysis, and figures.
   If you change weights, re-read `S6_weight_sensitivity.csv` — the robustness
   claim must be re-verified, not assumed.
2. **`norm()` uses log1p before min-max.** Flood counts are heavy-tailed
   (Gini ≈ 0.7–0.88); without the log, Bangkok-scale outliers would compress
   everyone else to ~0 and the score would be a one-variable ranking.
3. **Quintiles are cut on ranks**, not raw scores, so the 5-level classification
   cannot crash on ties (`pd.qcut` duplicate-edge error).
4. **Extent dimensions are excluded from scoring** (villages/subdistricts/
   districts affected) because 2020–2022 files double-count repeatedly-hit
   areas. They remain in the cleaned data for other uses.
5. **Statistical tests are deliberately non-parametric where n is small**
   (Mann-Kendall/Theil-Sen for n = 7 trends; Spearman everywhere; exact binomial
   for retention). Parametric OLS is reported alongside for familiarity, never
   alone.
6. **The original `02_analyze_visualize.py` is untouched** — its humanitarian
   composite remains valid for DDPM-style reporting; `03` is the credit view of
   the same cleaned data.
7. **Figures never restate results independently.** C5 plots the stored S6
   draws and the C4 caption is built from the computed `retention` table —
   figure and CSV cannot drift apart if the data or weights change.

## Revision history

| Date | Change | Statistics affected |
|---|---|---|
| 2026-06-12 | Senior code review (see ADJUSTMENT.md §5): C5 re-uses S6 draws instead of re-simulating with a second seed; C4 caption p-value computed from data; PCA loadings sign-flipped together with `pc1`; C5 histogram bins made data-driven | None — all CSV statistics byte-identical to the previous run |

# Adjustment: From General Flood Exposure to Credit-Risk Climate Overlay

This document records every change made to adapt the original analysis
(`02_analyze_visualize.py`) for **consumer credit risk modeling** across three
portfolios: **Mortgage**, **Business/SME loans (unlisted companies)**, and
**Automobile (hire-purchase)**.

The original script is untouched. The adjusted version is a new script,
**`03_credit_climate_risk.py`**, which reads the same cleaned data
(`data/province_year.csv` from `01_clean_prepare.py`). This preserves
reproducibility of the original humanitarian-oriented outputs while adding the
credit-oriented layer.

---

## 1. What changed and why

| # | Original (`02_analyze_visualize.py`) | Adjusted (`03_credit_climate_risk.py`) | Reason |
|---|---|---|---|
| 1 | One composite score with humanitarian weighting (human impact 30%, life-safety 20%, …) | **Three portfolio-specific scores** (mortgage, business/SME, automobile), each weighting only the dimensions that transmit into that portfolio's credit losses | A disaster-management ranking and a credit-loss ranking answer different questions. Deaths matter most to DDPM; collateral damage matters most to a mortgage book. |
| 2 | Weights asserted, not validated | Weights **validated two ways**: (a) Spearman agreement with a weight-free PCA benchmark, (b) 2,000-draw ±50% weight-perturbation sensitivity analysis | The user requirement "everything must be provable by statistics." A judgment-based weight scheme is acceptable **only if** the conclusions are shown to be insensitive to it. They are (see S2/S6 below). |
| 3 | OLS linear trend only | **Mann-Kendall test (Kendall's τ) + Theil-Sen robust slope**, OLS kept for reference | n = 7 annual observations with extreme years (2022, 2025). Non-parametric trend tests are robust to outliers and make no normality assumption — the honest choice for short, volatile series. |
| 4 | No persistence analysis | **Lag-1 Spearman rank correlation + top-quintile retention with exact binomial test** | The single most important fact for underwriting: past flood exposure must *predict* future exposure, otherwise the score is history, not risk. This is now tested, not assumed. |
| 5 | No concentration analysis | **Gini coefficient, Lorenz curves, top-10/top-20 province shares** | Concentration is the language of portfolio risk management. It converts "some provinces flood a lot" into a quantified concentration-limit argument. |
| 6 | All 15 dimensions in the score, including geographic-extent counts | **12 impact dimensions only** — villages/subdistricts/districts-affected counts are excluded from scoring | The 2020–2022 source files sum extent counts over events and double-count repeatedly-hit areas (documented in README caveats). Including them would make the score provably biased. THB damage is excluded because it exists only for 2019. |
| 7 | `pd.qcut` directly on scores | `pd.qcut` on **ranks** (`rank(method="first")`) | Guarantees the 5-level classification never fails on tied scores; identical result when scores are unique. |
| 8 | Outputs mixed with general analysis | Separate trees: `output/credit/`, `figures/credit/` | Keeps the credit evidence pack self-contained for presentation to a risk committee. |

---

## 2. Component re-mapping: original → portfolio-specific

### Original (humanitarian)

| Component | Dimensions | Weight |
|---|---|---|
| human_impact | affected people, households | 0.30 |
| life_safety | deaths, injured, evacuated | 0.20 |
| property | housing, business sites | 0.20 |
| agriculture | rai, livestock, fisheries | 0.10 |
| infrastructure | transport, public sites | 0.10 |
| frequency | years affected / 7 | 0.10 |

### Adjusted — Mortgage portfolio

| Component | Dimensions | Weight | Credit transmission channel |
|---|---|---|---|
| collateral_damage | housing_units | 0.35 | Direct physical damage to the mortgaged asset → LGD ↑, collateral value ↓ |
| borrower_disruption | affected_households | 0.25 | Income/payment interruption of household borrowers → PD ↑ (delinquency) |
| habitability_loss | evacuated_people | 0.10 | Severe displacement → prolonged non-occupancy, strategic default risk |
| area_recoverability | transport + infrastructure sites | 0.10 | Damaged public infrastructure slows local recovery and property-market liquidity |
| recurrence | years affected / 7 | 0.20 | Chronic flooding → structural value decline, insurance withdrawal/repricing |

### Adjusted — Business/SME loans (unlisted companies)

| Component | Dimensions | Weight | Credit transmission channel |
|---|---|---|---|
| business_interruption | business_sites | 0.30 | Direct damage to business premises → cash-flow break → PD ↑ |
| agri_sme_exposure | agriculture_rai, livestock, fisheries | 0.25 | Agricultural producers are overwhelmingly unlisted SMEs; crop/herd loss is a direct income shock |
| supply_chain | transport + infrastructure sites | 0.15 | Road/logistics damage interrupts revenue even for undamaged firms |
| local_demand_shock | affected_people | 0.10 | Flooded customer base → local revenue contraction |
| recurrence | years affected / 7 | 0.20 | Repeated interruption → working-capital erosion, viability risk |

### Adjusted — Automobile / hire-purchase portfolio

| Component | Dimensions | Weight | Credit transmission channel |
|---|---|---|---|
| vehicle_damage_proxy | housing_units | 0.25 | Vehicles flood where homes flood (parked at residence); housing damage is the best available proxy — **stated as a proxy, see limitations** |
| owner_base_affected | affected_households | 0.25 | Size of the affected household base ≈ affected vehicle-owning population |
| sudden_onset | evacuated_people | 0.15 | Evacuation events leave no time to relocate vehicles → total-loss frequency ↑ |
| road_disruption | transport_sites | 0.15 | Road damage → usage loss, collateral valuation, repossession logistics cost |
| recurrence | years affected / 7 | 0.20 | Repeat inundation → resale value decline in the local used-car market |

All weight sets sum to 1.0. Within a component, multiple dimensions are
log1p-transformed, min-max normalized, then **averaged** before the weight is
applied — identical normalization to the original script, so cross-script
results remain comparable.

---

## 3. Statistical layer added (the "provability" requirement)

| ID | Test | Question it answers | Output file |
|---|---|---|---|
| S1 | Spearman correlation matrix (12 dims) | Are the within-component groupings supported by the data? | `S1_dimension_spearman_corr.csv` |
| S2 | PCA + agreement with portfolio scores | Are the rankings an artifact of the chosen weights? | `S2_pca_loadings.csv`, `S2_pca_validation.csv` |
| S3 | Mann-Kendall + Theil-Sen + OLS per dimension | Is national exposure trending, and is the trend statistically significant? | `S3_trend_tests.csv` |
| S4 | Lag-1 Spearman + top-quintile retention (exact binomial) | Does past exposure predict future exposure? | `S4_persistence_by_yearpair.csv`, `S4_persistence_summary.csv` |
| S5 | Gini / Lorenz / top-shares | How concentrated is the exposure geographically? | `S5_concentration.csv` |
| S6 | 2,000-draw weight perturbation (±50%) | Do the top-20 lists survive weight uncertainty? | `S6_weight_sensitivity.csv` |

Key validation results from the actual run (full numbers in `EXPLANATION.md`):

- **S2:** PC1 of a weight-free PCA explains **53.2%** of cross-province variance;
  the three portfolio scores correlate with PC1 at Spearman ρ = **0.93 / 0.90 / 0.94**
  (all p < 10⁻²⁸). The rankings are driven by the data, not the weights.
- **S6:** perturbing every weight by ±50% (2,000 draws), the top-20 lists keep on
  average **18.4–19.5 of 20** provinces; full-ranking Spearman vs baseline ≥ **0.98**
  in the 5th percentile. The weight choice is not load-bearing.

---

## 4. What was deliberately *not* done

- **No synthetic credit data.** No PD/LGD/NPL numbers were invented. The output is
  an *exposure overlay* — the statistically defensible step possible with public
  DDPM data alone. The next step (joining bank portfolio data) is specified in
  `EXPLANATION.md` §6.
- **No causal claims.** The analysis claims materiality, persistence, and
  concentration of physical exposure — each backed by a test — and documents the
  transmission channels to credit risk. It does not claim a measured PD uplift.
- **No cherry-picking.** All 12 dimensions' trend tests are reported, including
  the non-significant ones (e.g., agriculture_rai: τ = −0.05, p = 1.00).

---

## 5. Refinements (2026-06-12)

A senior review of `03_credit_climate_risk.py` confirmed the methodology and
all results, and applied three behavior-preserving refinements. **No statistic
in any output CSV changed** — verified by re-running and comparing against the
previous run.

| # | Change | Before | After | Why |
|---|---|---|---|---|
| 1 | Figure C5 re-uses the stored S6 simulation draws (`sens_overlaps`) | C5 re-ran the 2,000-draw simulation with a *second* seed (7), so the histogram means differed from `S6_weight_sensitivity.csv` in the second decimal (e.g., 18.47 vs 18.43 for mortgage) | C5 plots the exact draws behind the S6 CSV (seed 42); one simulation, one set of numbers | Figure and CSV can never disagree; also removes a duplicated 2,000-draw loop |
| 2 | Figure C4 caption p-value is computed | Caption hardcoded "all binomial p-values < 0.001" — true today, but would silently become wrong on a data update | Caption built from the data: `largest binomial p-value = {retention['binom_p_value'].max():.1e}` (currently 3.5e-08) | A figure must not assert a result the code did not compute from the current data |
| 3 | PCA loadings sign-flipped together with `pc1` | The orientation guard flipped the `pc1` score series but not the loadings written to `S2_pca_loadings.csv` — a *latent* inconsistency (the flip does not trigger with current data: all PC1 loadings are already positive) | `pca.components_[0] *= -1` inside the same guard, so the saved loadings always match the orientation used for validation | Defensive consistency if future data changes the PCA orientation |

Alongside #1, the C5 histogram bin range (previously hardcoded to start at
13.5) was made data-driven (`min(ovl.min(), 14) − 0.5`), so no simulation draw
can ever fall outside the plotted range.

Two further observations were reviewed and **deliberately left as-is**:

- The pooled binomial test in S4 uses a 20% base rate while the exact rate is
  16/77 ≈ 20.8% (and a per-pair hypergeometric would be exact). With observed
  p-values ≤ 3.5 × 10⁻⁸, the approximation cannot change any conclusion.
- The projection band is the in-sample ±1 residual SE, not a full prediction
  interval (no extrapolation-leverage term). The figure and EXPLANATION.md
  already present the projections as trend indications, not forecasts.

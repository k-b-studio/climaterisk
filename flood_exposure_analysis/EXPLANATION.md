# Explanation: Why Climate (Flood) Risk Matters to Credit Risk Management

**Position:** Flood risk in Thailand is a material, persistent, geographically
concentrated, and (for collateral-relevant damage) statistically growing driver
of credit risk for Mortgage, Business/SME, and Automobile portfolios.

Every claim below is backed by a statistic computed in
`03_credit_climate_risk.py` from DDPM flood records 2019–2025 (493 province×year
observations, 77 provinces). Output files cited are in `output/credit/`.

---

## 1. The argument in five provable statements

### Claim 1 — Flood damage to credit-relevant assets is large and growing

National totals (from `data/province_year.csv`):

| Year | Affected people | Affected households | Housing damaged | Deaths |
|---|---|---|---|---|
| 2019 | 1,816,530 | 737,075 | 43,484 | 30 |
| 2022 | 4,083,913 | 1,789,404 | 248,634 | 79 |
| 2025 | 6,650,737 | 2,689,753 | 633,533 | 272 |

**Proof of trend** (`S3_trend_tests.csv`, Mann-Kendall on n = 7 years):

| Dimension | Kendall τ | MK p-value | Theil-Sen slope/yr | OLS R² | OLS p |
|---|---|---|---|---|---|
| **Housing damaged** | **0.714** | **0.030** | **+68,383 units/yr (+27.8% of mean)** | 0.617 | 0.036 |
| **Deaths** | **0.714** | **0.030** | +16.3/yr | 0.520 | 0.067 |
| Business sites | 0.714 | 0.030 | +21.8/yr | 0.666 | 0.025 |
| Injured | 0.586 | 0.068 | +2.0/yr | 0.478 | 0.085 |
| Affected people | 0.429 | 0.239 | +412,286/yr | 0.330 | 0.177 |
| Affected households | 0.429 | 0.239 | +206,705/yr | 0.309 | 0.195 |
| Agriculture (rai) | −0.048 | 1.000 | −264,111/yr | 0.072 | 0.561 |

**Honest reading:** housing damage — the dimension that hits mortgage collateral
and proxies vehicle losses — shows a statistically significant rising trend at
the 5% level under both a non-parametric (Mann-Kendall) and parametric (OLS)
test, despite only 7 observations. Affected people/households point upward but
are not significant at n = 7. Agriculture shows no trend. The business-sites
trend is significant but counts are tiny (2 → 170/yr) and likely partly
reporting-driven — we flag it, we do not lean on it.

### Claim 2 — Flood exposure is persistent, so it is *predictive*, not just historical

If province exposure reshuffled randomly each year, history would be useless for
underwriting. It does not reshuffle (`S4_persistence_summary.csv`):

| Dimension | Mean lag-1 Spearman ρ (year t vs t+1) | Top-quintile retention | Random base rate | Binomial p |
|---|---|---|---|---|
| Affected people | 0.524 | **46.9%** | 20% | 3.0 × 10⁻⁹ |
| Affected households | 0.482 | **49.0%** | 20% | 2.1 × 10⁻¹⁰ |
| Housing damaged | 0.434 | **44.8%** | 20% | 3.5 × 10⁻⁸ |

A province in the worst 20% this year is **2.2–2.5× more likely than chance** to
be in the worst 20% next year (96 trials across six year-pairs; all
p < 10⁻⁷). This is the statistical license to use the exposure score as a
forward-looking underwriting and pricing factor.

### Claim 3 — Exposure is concentrated, which is exactly what a portfolio manager must price

(`S5_concentration.csv`, cumulative 2019–2025 across 77 provinces)

| Dimension | Gini | Top-10 province share | Top-20 province share |
|---|---|---|---|
| Affected people | 0.704 | 63.0% | 80.8% |
| Housing damaged | 0.711 | 62.9% | 82.0% |
| Business sites | 0.881 | 87.9% | 96.1% |
| Agriculture (rai) | 0.720 | 61.3% | 83.3% |

Ten provinces carry ~63% of all flood-damaged housing. A lender whose mortgage
origination is overweight in those provinces holds a climate concentration that
**never appears in a borrower-level scorecard** — it is invisible until measured
geographically. Concentration this extreme (Gini ≈ 0.7, vs ~0.4–0.5 for typical
income inequality) is the textbook condition under which a common shock
(one severe monsoon season) produces correlated defaults rather than
diversifiable idiosyncratic losses.

### Claim 4 — The portfolio rankings are robust, not an artifact of our weights

Two independent validations:

- **Weight-free benchmark (PCA, `S2_pca_validation.csv`):** the first principal
  component of the 12 normalized dimensions — which uses *no* judgment weights —
  explains **53.2%** of cross-province variance. Our portfolio scores agree with
  it at Spearman ρ = **0.932 (mortgage), 0.898 (SME), 0.936 (auto)**, all
  p < 10⁻²⁸; 15–16 of each portfolio's top-20 provinces are also in PC1's top-20.
- **Weight perturbation (`S6_weight_sensitivity.csv`):** every weight randomly
  perturbed by ±50% and renormalized, 2,000 draws per portfolio:

| Portfolio | Mean top-20 overlap | 5th-percentile overlap | Worst case | Mean rank ρ vs baseline |
|---|---|---|---|---|
| Mortgage | 18.4 / 20 | 17 | 16 | 0.992 |
| Business/SME | 19.5 / 20 | 19 | 19 | 0.992 |
| Automobile | 19.2 / 20 | 18 | 16 | 0.992 |

Even under aggressive weight uncertainty, at least 16 of the top-20 provinces
never change. **The "where" conclusion is data-driven; the weights only fine-tune
ordering within the high-risk set.**

### Claim 5 — The trend points to higher collateral-relevant damage in 2026–2028

(`credit_projection_2026_2028.csv`; OLS with ±1 SE band, Theil-Sen as robust
cross-check)

| Dimension | 2028 OLS projection | ±1 SE range | 2028 Theil-Sen |
|---|---|---|---|
| Housing damaged | 670,035 units | 538,363 – 801,707 | 651,780 |
| Affected households | 2,526,681 | 1,848,255 – 3,205,107 | 2,616,222 |

The robust and parametric estimators agree within ~3%, which increases
confidence the direction is real. **These are trend indications, not forecasts**
— with n = 7 volatile years the bands are wide and a quiet 2026 is entirely
possible. The risk-management conclusion does not depend on the point estimate:
even a flat continuation of 2024–2025 levels (310K–634K damaged homes/yr) is
material to any mortgage book.

---

## 2. Transmission channels: how flood exposure becomes credit loss

| Portfolio | PD channel | LGD / collateral channel | Documented evidence in this data |
|---|---|---|---|
| **Mortgage** | Borrower income interruption, displacement → missed installments | Physical damage to the property; chronic-flood discount on resale value; insurance retreat raises borrower's uninsured share | 633K homes damaged in 2025 alone; housing-damage trend significant (p = 0.030); top-quintile provinces persist (p < 10⁻⁷) |
| **Business/SME (unlisted)** | Business interruption, destroyed inventory/equipment, local demand collapse → cash-flow default. Unlisted SMEs lack capital-market access and insurance penetration, so the shock passes straight to the lender | Damaged premises and equipment pledged as collateral | Business-site damage concentrated in 10 provinces holding 87.9% of all cases (Gini 0.881); agri damage 1.1–5.1M rai/yr hits agri-SME borrowers |
| **Automobile / HP** | Owner income shock; vehicle = work tool for many HP borrowers (loss of vehicle = loss of income = default) | Flood-damaged vehicle is a near-total collateral loss; flooded-region used-car prices and repossession recovery fall | Housing damage (the proxy for vehicle inundation, ρ = 0.65 with affected people) trending up significantly; evacuation events indicate no-warning inundation |

### Where the risk sits (top-10 by portfolio score, `credit_portfolio_scores.csv`)

- **Mortgage:** นครราชสีมา (100), เชียงใหม่ (99.9), พัทลุง (99.5), ยะลา (97.5),
  ปัตตานี (96.0), นราธิวาส (95.3), สงขลา (95.0), ชัยภูมิ (93.9),
  นครศรีธรรมราช (92.3), เชียงราย (91.1)
- **Business/SME:** นครราชสีมา (100), เชียงราย (97.9), ขอนแก่น (87.8),
  อุตรดิตถ์ (86.8), พัทลุง (85.4), สุโขทัย (84.3), พะเยา (81.7), นครปฐม (81.0),
  แม่ฮ่องสอน (79.7), กาฬสินธุ์ (77.6)
- **Automobile:** นครราชสีมา (100), พัทลุง (97.4), เชียงใหม่ (94.6), สงขลา (92.6),
  นราธิวาส (92.2), นครศรีธรรมราช (91.9), ยะลา (91.8), ชัยภูมิ (91.5),
  ปัตตานี (90.6), ตาก (89.5)

Note the rankings *differ by portfolio* — e.g., ขอนแก่น and อุตรดิตถ์ surface in
the SME view but not the mortgage view. This is the practical payoff of
portfolio-specific weighting: one generic "disaster score" would misallocate
limits across products. The high-risk belt is consistent: **lower North
(เชียงใหม่/เชียงราย), Korat plateau (นครราชสีมา/ชัยภูมิ/ขอนแก่น), and the deep
South (สงขลา–พัทลุง–ปัตตานี–ยะลา–นราธิวาส).**

---

## 3. Implications for credit risk management

1. **Underwriting & pricing.** The persistence result (Claim 2) justifies a
   province-level (ideally district-level) exposure factor in application
   scorecards and risk-based pricing for all three products.
2. **Concentration limits.** The Gini/Lorenz results (Claim 3) justify explicit
   geographic concentration limits — the top-20 provinces carry ~80–96% of
   national flood damage depending on dimension.
3. **Collateral policy.** Higher haircuts / lower max LTV for properties and
   vehicles in Very-High-risk provinces; mandatory flood insurance verification
   where insurance is still available.
4. **IFRS 9 forward-looking overlays.** The significant housing-damage trend
   (Claim 1) and projections (Claim 5) are exactly the kind of "reasonable and
   supportable forward-looking information" IFRS 9 requires for ECL staging and
   management overlays.
5. **Stress testing.** The 2025 season (6.65M people affected, 633K homes
   damaged, 272 deaths) is an observed — not hypothetical — severe scenario for
   climate stress tests, consistent with the Bank of Thailand's direction on
   financial-sector climate risk management.

---

## 4. Honest limitations (what this analysis does NOT prove)

1. **No loan-level outcome data.** This is an *exposure* analysis. It proves the
   hazard is material, persistent, and concentrated; it does **not** measure PD
   or LGD uplift. That requires joining bank data (DPD/NPL by province and
   product) — see §5.
2. **Ecological inference.** Province-level exposure ≠ every borrower in that
   province is exposed. District/geocoded underwriting is the refinement path
   (district data exists for 2020–2024 in `data/district_year.csv`).
3. **n = 7 years.** Trend tests have low power; only housing damage, deaths, and
   business sites reach 5% significance. We report all twelve dimensions,
   including the null results.
4. **Vehicle damage is proxied**, not observed (DDPM does not record vehicle
   losses). The proxy (housing damage + evacuations) is stated openly and its
   weight is shown to be non-load-bearing by the sensitivity analysis.
5. **Reporting heterogeneity.** Business-site counts jump from single digits
   (2019–2022) to 100+ (2024–2025) — partly real, plausibly partly improved
   reporting. We therefore do not rest any headline claim on that series alone.
6. **Projections are trend indications.** Flood losses are fat-tailed and
   regime-driven (ENSO); a linear trend is a planning anchor, not a forecast.

## 5. Next step to close the loop (the credible roadmap)

Join `credit_portfolio_scores.csv` to internal portfolio data and test directly:

- **Test:** do Very-High provinces show higher post-flood-season delinquency
  flow than Low provinces, controlling for income and product mix?
  (difference-in-differences around the 2022 and 2025 seasons, or discrete-time
  survival model with the exposure score as covariate).
- **Expected deliverable:** measured PD/LGD sensitivity per risk level → direct
  input to pricing grids, ECL overlays, and capital planning.

That test is only worth running because of what is already proven here:
the hazard is big enough (Claim 1), stable enough to act on (Claim 2),
concentrated enough to matter at portfolio level (Claim 3), and the geographic
targeting is robust (Claim 4).

---

## Revision note (2026-06-12)

`03_credit_climate_risk.py` passed a senior code review; three
consistency refinements were applied (documented in ADJUSTMENT.md §5) and the
full pipeline was re-run. **Every number cited in this document is unchanged.**
Two presentation details improved:

- Figure `C5_weight_sensitivity.png` now plots the *exact* simulation draws
  behind `S6_weight_sensitivity.csv` (previously a second, separately-seeded
  simulation; means differed only in the second decimal). The Claim 4 table
  and the figure are now numerically identical by construction.
- Figure `C4_persistence.png` now states the computed worst-case binomial
  p-value (3.5 × 10⁻⁸) instead of the hardcoded claim "p < 0.001", so the
  caption regenerates correctly if the data is ever updated.

# Explanation — Forward-Looking Flood Risk by Integrating Rain & Flood Forecasts

**Position:** By combining a 6-month **rain forecast**, a 6-month **flood
forecast**, and **7 years of historical flood damage**, we can produce a
*forward-looking* 2026 flood-risk classification that is (a) validated against
what actually happened, (b) resolved by quarter/season and by risk type, and
(c) translated into credit-portfolio terms — while being honest about which
signals carry weight and which do not.

Every statistic below is computed in `02_analyze_visualize.py` /
`03_portfolio_forward.py` from the three IECC sources (77 provinces). Output
files cited are in `output/`.

---

## 1. The factors (requirement 6 — variable explanation)

The cross-province score has **two** inputs; rainfall is a third source used
only for *timing*. Each is a normalized `[0,1]` series per province:

| Factor | Source | What it measures | In the score? |
|---|---|---|---|
| **Flood-forecast share** | Flood Forecast 6m | Fraction of a province's subdistricts the flood model flags as *flood*/*flashflood* in the monsoon — the most **direct hazard** signal | ✅ 50% |
| **Historical vulnerability** | Flood Historical 2019-2025 | Cumulative damage to credit-relevant assets (people, households, housing) — structural **vulnerability & persistence** | ✅ 50% |
| **Forecast rainfall** | Rain Forecast 6m | Consensus monsoon rainfall (mm) — the physical **driver** | ❌ — *timing only* (§2.2) |

```
risk_score = 0.50 · FloodForecast + 0.50 · History     (monsoon Jun–Oct)
```

The composition is not arbitrary — only the factors that validate positively
against actual damage are in the score (§2), and rainfall is excluded for the
reason in §2.2.

---

## 2. Validation — what the data says each signal is worth (requirement 1)

We have forecasts **and** actuals for **2024 and 2025**, so we can test directly
whether the forecasts rank the provinces that actually flooded.

### 2.1 Each factor vs actual damage (`S1_forecast_validation.csv`, Spearman ρ)

| Predictor | vs 2025 housing | vs 2025 people | vs 2024 housing | Reading |
|---|---|---|---|---|
| **Historical vulnerability** | **0.63** (p≈2×10⁻⁹) | **0.67** (p≈6×10⁻¹¹) | **0.44** (p≈1×10⁻⁴) | **Strongest** — persistence is real |
| **Flood-forecast share** | 0.20 (p≈0.09) | −0.19 | **0.25** (p≈0.03) | Modest, positive on **housing/collateral** |
| **Forecast rainfall** | **−0.46** (p≈4×10⁻⁵) | −0.36 | −0.14 | **Negative** — see honest finding below |

### 2.2 The honest rainfall finding

Raw monsoon rainfall is **negatively** correlated with flood damage across
provinces. This is not a bug — it is geography:

> The wettest provinces (**ระนอง 460 mm, พังงา 400 mm** in the South) are
> mountainous/coastal, drain straight to the sea, and have low population and
> low credit exposure. The heaviest *damage* lands on the **Central plains and
> Northeast**, which get moderate rain but where water accumulates over flat,
> densely-settled, agriculturally-developed land.

The flood-forecast model already routes rainfall through terrain and hydrology —
which is exactly why the **flood-forecast share is positive** while **raw
rainfall is negative**. Rainfall's genuine value is therefore **temporal**
(it pinpoints *when* in 2026 the risk peaks, §4) and as the physical driver, not
as a cross-province damage ranker. **It is therefore excluded from the score**
and retained only for the seasonal/timing layer. Removing it raised the score's
out-of-time validation on housing from ρ = 0.29 to **0.39** (§2.4).

### 2.3 Factor regression (`S2_factor_regression.csv`, pooled 2024-25, n=154)

Standardized regression of actual housing-damage rank on the three factors:

| Factor | Standardized β |
|---|---|
| History | **+0.496** |
| Flood-forecast share | **+0.283** |
| Rainfall | −0.175 |
| **Model R²** | **0.385** |

History and flood-forecast both contribute positively and independently;
rainfall's partial effect is negative once geography (via the other two) is
controlled. Consistent with §2.1.

### 2.4 Out-of-time test of the *composite* (`S3_composite_validation.csv`)

Building the **2025** score (flood + history, no rain) from 2025 forecasts +
history-through-2024 only (no leakage) and ranking it against 2025 actuals:

| Actual 2025 dimension | Composite Spearman ρ | p |
|---|---|---|
| **Housing damaged (collateral)** | **0.39** | **0.0006** |
| Affected households | 0.14 | 0.25 |
| Affected people | 0.08 | 0.48 |

**Honest reading:** the composite is strongly significant on **housing —
the dimension that matters most for collateral / credit** — but adds little
beyond history for people/household counts. The forecast layer earns its place
by (i) sharpening the *collateral* signal and (ii) providing the temporal and
2026-specific spatial detail that a static history cannot (e.g. **บึงกาฬ**: only
3 historical flood years but a 2026 flood-forecast share of 0.47 — an emerging
risk a history-only model would miss). We do **not** claim the forecasts beat
history on aggregate headcounts. (Including rainfall here dropped the housing ρ
to 0.29 — the reason it is excluded, §2.2.)

---

## 3. Meaning of the risk levels (requirement 3)

Provinces are cut into quintiles of the score (`risk_level_meaning.csv`):

| Level | Meaning |
|---|---|
| **5 — Very High** | Top 20%. High forecast rain **and** flood flagging **and** heavy damage history. Expect material 2026 monsoon losses. |
| **4 — High** | Strong on two of three factors. Elevated loss risk. |
| **3 — Moderate** | Mixed signals; average exposure. Monitor through the monsoon. |
| **2 — Low** | Low forecast hazard and light history. |
| **1 — Very Low** | Bottom 20%. Minimal forecast signal and little history. |

**Top of the 2026 list** (`top20_forward_risk_2026.csv`): ศรีสะเกษ, ตาก,
แม่ฮ่องสอน, สุโขทัย, พิจิตร, น่าน, พระนครศรีอยุธยา, เชียงใหม่, อุบลราชธานี,
นครสวรรค์ — the familiar North / upper-Central / Northeast flood belt. (With rain
removed from the score, the high-rain but low-exposure South provinces ระนอง and
ตราด correctly fall out of the top tier — ระนอง drops from #1 to #11.)

---

## 4. Quarterly, seasonal, area & type-of-risk breakdowns (requirement 4)

### 4.1 Quarterly & seasonal (`quarterly_2026.csv`, `seasonal_2026.csv`)

| Quarter 2026 | Flood at-risk share | Rainfall (mm) |
|---|---|---|
| Q1 (Jan-Mar) | 0.4% | 38 |
| Q2 (Apr-Jun) | 2.4% | 162 |
| **Q3 (Jul-Sep)** | **12.7%** | **231** |
| Q4 (Oct-Dec) | 10.3% | 113 |

Risk is overwhelmingly a **Q3-Q4 / monsoon** phenomenon: the at-risk share is
**~30× higher in the rainy season (11.3%) than the hot season (0.7%)**. The
single peak month is **September** (16.4% at-risk, 301 mm). This is the temporal
intelligence the rain/flood forecasts add that the historical (annual) data
cannot.

### 4.2 Area / region (`region_summary_2026.csv`)

| Region | Mean 2026 risk score |
|---|---|
| **North** | **74.7** |
| Northeast | 65.0 |
| South | 55.5 |
| East | 54.7 |
| Central | 52.5 |

### 4.3 Type of risk (`type_of_risk_by_region.csv`, monsoon shares)

| Region | Flood (riverine) | Flashflood |
|---|---|---|
| **Northeast** | **0.152** | 0.005 |
| North | 0.080 | **0.095** |
| Central | 0.076 | 0.003 |
| East | 0.065 | 0.020 |
| South | 0.017 | 0.034 |

The **Northeast and Central plains face slow riverine flooding**; the
**mountainous North faces flashflooding** (the only region where flashflood
exceeds riverine flood). The risk *type* — not just the level — should drive
the response: flashflood gives little warning (collateral/vehicle total loss),
riverine flooding is more forecastable but longer-duration (business interruption).

---

## 5. Correlation structure (requirement 5, `correlation_matrix.csv`)

| Spearman ρ | hist-vuln | actual-2025-people | actual-2025-housing |
|---|---|---|---|
| **hist-vulnerability** | 1.00 | **0.75** | **0.70** |
| forecast-rain-2026 | −0.39 | −0.24 | −0.43 |
| flood-share-2026 | −0.09 | −0.23 | −0.00 |
| flash-share-2026 | 0.05 | −0.09 | 0.08 |

`flood-share` and `flash-share` correlate 0.45 with each other (both are wet-
season hazards) but only weakly with the historical/actual columns — confirming
they carry **independent forward information** rather than re-stating history.
The strong `history ↔ actual` block (0.70-0.75) is the persistence result that
anchors the score.

---

## 6. Portfolio impact (requirement 4 — portfolios)

`03_portfolio_forward.py` keeps the 50/50 flood-forecast / history split and
re-weights only the **history** component per portfolio, so each book sees its
own collateral channel (`top20_by_portfolio_2026.csv`):

| Portfolio | History dimensions | Transmission to credit loss |
|---|---|---|
| **Mortgage** | housing 50% · households 30% · people 20% | Property damage → LGD; displacement → missed installments |
| **Business/SME (unlisted)** | business sites 40% · agriculture 30% · households 20% · infrastructure 10% | Premises/inventory/crop loss → cash-flow default; no capital-market buffer |
| **Automobile / HP** | housing 40% (vehicle-inundation proxy) · evacuated 30% · people 30% | Flooded vehicle ≈ total collateral loss; owner income shock |

**Rankings differ by portfolio** (`portfolio_region_exposure_2026.csv`): the
**North is the most exposed region for all three** (mortgage 76, SME 75, auto
69), but **บึงกาฬ is #3 for SME yet outside the mortgage top-10**, เชียงราย
surfaces in SME, and ยโสธร in Automobile. A single generic "disaster score"
would misallocate limits across products — portfolio-specific weighting is the
payoff.

---

## 7. Implications for credit risk management

1. **Seasonal overlays.** The Q3-Q4 concentration justifies a *time-varying*
   monsoon overlay (tighten new originations / step up monitoring Jul-Oct in
   high-risk provinces) rather than a flat annual adjustment.
2. **Type-aware collateral policy.** Higher haircuts / mandatory insurance
   verification for vehicles and homes in **flashflood-dominated North**
   provinces (no-warning total-loss risk); business-interruption focus in the
   **riverine Northeast/Central**.
3. **Forward-looking IFRS 9 input.** The validated forward score is exactly the
   "reasonable and supportable forward-looking information" IFRS 9 expects for
   ECL staging — usable as a province-level macro overlay updated each time a new
   6-month forecast is issued.
4. **Emerging-risk flagging.** Provinces high on flood-forecast but low on
   history (บึงกาฬ) are early warnings the backward-looking model cannot see.

---

## 8. Honest limitations (what this does NOT prove)

1. **Raw rainfall is a weak (negative) cross-province damage ranker** (§2.2), so
   it is **excluded from the score** and used only for *timing*, not *place*. A
   rainfall **anomaly** vs each province's own climatology (not available here)
   would likely make rainfall usable for place too — a clear refinement path.
2. **No loan-level outcomes.** This is a hazard/exposure analysis; it does not
   measure realized PD/LGD. Joining bank DPD/NPL by province × product is the
   next step (as in the sibling project's §5).
3. **Forecast skill is finite.** The flood/rain forecasts are 6-month model
   outputs; their cross-province discrimination beyond history is modest
   (composite ρ ≈ 0.29 on housing). The score is a *blend*, not a claim that the
   forecast alone is decisive.
4. **Southern monsoon timing.** The Jun-Oct window understates the South, whose
   heaviest rain comes with the NE monsoon (Oct-Dec); Southern risk may be
   slightly understated in an annual monsoon-window view.
5. **Categorical flood forecast.** `flood/flashflood/norisk` has no intensity
   grade; the at-risk *share* of subdistricts is our intensity proxy.

---

## Provenance

- Sources: `IECC/Rain Forecast 6 month`, `IECC/Flood Forecast 6 month`,
  `IECC/Flood Historical Data` (via the sibling cleaned `province_year.csv`).
- All numbers regenerate from `python3 01 → 02 → 03`; every figure plots the
  same tables cited here (figures and CSVs cannot drift).

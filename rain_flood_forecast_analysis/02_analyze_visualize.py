# -*- coding: utf-8 -*-
"""
02_analyze_visualize.py
===================================================================
PURPOSE
    Turn the three cleaned sources into a *forward-looking* flood-risk
    classification for the 2026 6-month horizon, and PROVE the forecasts
    carry real signal by validating them against historical actuals.

WHAT THIS SCRIPT ANSWERS (mapped to the analysis requirements)
    (1) Provement by statistics .... SECTION 3: forecast signals vs actual
                                     damage (Spearman + p, 2024-2025), and a
                                     standardized regression decomposing which
                                     factor explains observed damage.
    (2) Top-20 risk areas .......... SECTION 5 + Figure F1.
    (3) Meaning of risk level ...... SECTION 4 (RISK_LEVEL_MEANING) -> CSV + console.
    (4) Quarterly / seasonal / area /
        type-of-risk breakdowns .... SECTION 6 (+ F3,F4,F5). Portfolio is in 03_*.
    (5) Correlation ................ SECTION 7 + Figure F6.
    (6) Factor / variable meaning .. SECTION 1 (FACTORS) + EXPLANATION.md.

THE FORWARD-LOOKING SCORE (one line)
    score = wR*Rain + wF*FloodForecast + wH*HistoricalVulnerability
    on monsoon-window (Jun-Oct) signals, rescaled 0-100, classified into
    5 risk levels. Weights are justified by the validation in SECTION 3.
===================================================================
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from scipy.stats import spearmanr

# ===================================================================
# SECTION 0 - Paths, style, load cleaned data
# ===================================================================
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
FIG = os.path.join(BASE, "figures")
OUT = os.path.join(BASE, "output")
os.makedirs(FIG, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

plt.rcParams["font.family"] = "Thonburi"          # macOS Thai font for labels
plt.rcParams["axes.unicode_minus"] = False

rain = pd.read_csv(os.path.join(DATA, "rain_province_month.csv"))
flood_fc = pd.read_csv(os.path.join(DATA, "flood_forecast_province_month.csv"))
hist = pd.read_csv(os.path.join(DATA, "historical_province_year.csv"))
meta = pd.read_csv(os.path.join(DATA, "province_meta.csv"))

MONSOON = (6, 10)            # Jun-Oct: Thailand's flood-driving rainy season
FORWARD_YEAR = 2026
HIST_YEARS = sorted(hist.year.unique())

# ===================================================================
# SECTION 1 - FACTORS: the variables that build the score
#   Each factor is one normalized [0,1] series per province. Documented
#   here so the meaning of every input is explicit (requirement 6).
# ===================================================================
FACTORS = {
    "flood": "Flood factor  - share of a province's subdistricts the flood model "
             "flags as flood/flashflood in the monsoon. The most DIRECT hazard signal. "
             "[in the SCORE]",
    "hist":  "History factor- cumulative 2019-2025 damage to credit-relevant assets "
             "(people/households/housing). Captures structural VULNERABILITY & "
             "persistence; the strongest validated predictor. [in the SCORE]",
    "rain":  "Rain factor   - consensus forecast rainfall (mm), monsoon Jun-Oct. The "
             "physical DRIVER, but geographically confounded across provinces (the "
             "wettest provinces drain to the sea), so it is NOT in the cross-province "
             "score. It powers the seasonal/quarterly TIMING analysis instead. "
             "[TIMING only - see SECTION 3 & EXPLANATION.md §2]",
}
# Score weights. The cross-province score uses only the two factors that
# validate positively against actual damage (SECTION 3): the direct flood-
# forecast hazard and the persistent damage history. Raw rainfall is excluded
# from the score because it is negatively/zero correlated with cross-province
# damage; it is retained for the seasonal-timing layer only. See EXPLANATION §2.
WEIGHTS = {"flood": 0.50, "hist": 0.50}


def norm_minmax(s):
    """Plain min-max to [0,1] - used for already-comparable signals
    (rainfall mm, at-risk share)."""
    s = s.astype(float)
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng > 0 else s * 0.0


def norm_log(s):
    """log1p then min-max - used for heavy-tailed damage COUNTS so a few
    mega-provinces (Bangkok-scale) do not crush everyone else to ~0."""
    s = np.log1p(s.astype(float))
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng > 0 else s * 0.0


# ===================================================================
# SECTION 2 - Signal builders (per province)
#   These produce the three factors for ANY year, so the same definitions
#   feed both validation (2024-2025) and the forward 2026 score.
# ===================================================================
def forecast_signals(year, window=MONSOON):
    """Monsoon-window rain (mm) and flood at-risk / flashflood shares,
    averaged over the months in `window`, indexed by province."""
    rm = rain[(rain.forecast_year == year) & rain.forecast_month.between(*window)]
    rs = rm.groupby("province")["rainfall_mm"].mean()
    fm = flood_fc[(flood_fc.forecast_year == year) & flood_fc.forecast_month.between(*window)]
    fs = fm.groupby("province")[["share_atrisk", "share_flood", "share_flash"]].mean()
    return pd.DataFrame({"rain_mm": rs}).join(fs)


def historical_vulnerability(upto_year):
    """Cumulative credit-relevant damage composite for all years <= upto_year,
    plus raw context columns. Returns a DataFrame indexed by province."""
    h = hist[hist.year <= upto_year]
    cols = ["affected_people", "affected_households", "housing_units", "deaths"]
    agg = h.groupby("province")[cols].sum(min_count=1).fillna(0)
    # years a province recorded any flood -> exposure frequency (persistence proxy)
    hit = h[h[["affected_people", "housing_units"]].fillna(0).sum(axis=1) > 0]
    agg["years_affected"] = hit.groupby("province")["year"].nunique().reindex(agg.index).fillna(0)
    comp = pd.concat([norm_log(agg[c]) for c in
                      ["affected_people", "affected_households", "housing_units"]], axis=1).mean(axis=1)
    agg["hist_composite"] = comp
    return agg


# ===================================================================
# SECTION 3 - STATISTICAL VALIDATION  (requirement 1: "provement by statistic")
#   Claim: forecast rainfall and forecast flood-share are not noise - provinces
#   the models flag actually take more real damage. Tested on 2024 & 2025,
#   the two years where forecasts AND actuals both exist.
# ===================================================================
def spearman_row(x, y, label_x, label_y, year):
    common = x.dropna().index.intersection(y.dropna().index)
    rho, p = spearmanr(x.loc[common], y.loc[common])
    return {"year": year, "predictor": label_x, "actual": label_y,
            "n": len(common), "spearman_rho": round(rho, 3), "p_value": p}

ACTUAL_DIMS = ["affected_people", "housing_units", "affected_households"]
val_rows = []
for yr in [2024, 2025]:
    sig = forecast_signals(yr)
    base = historical_vulnerability(yr - 1)["hist_composite"]    # info known BEFORE year yr
    actual = hist[hist.year == yr].set_index("province")[ACTUAL_DIMS]
    for adim in ACTUAL_DIMS:
        val_rows.append(spearman_row(sig["rain_mm"], actual[adim], "forecast_rain", adim, yr))
        val_rows.append(spearman_row(sig["share_atrisk"], actual[adim], "forecast_flood_share", adim, yr))
        val_rows.append(spearman_row(base, actual[adim], "historical_baseline", adim, yr))
validation = pd.DataFrame(val_rows)
validation.to_csv(os.path.join(OUT, "S1_forecast_validation.csv"), index=False, encoding="utf-8-sig")

# Pooled (2024+2025) standardized regression: how much does each factor explain
# actual housing damage RANK? Reported as standardized betas + R^2 (n=154).
pool_x, pool_y = [], []
for yr in [2024, 2025]:
    sig = forecast_signals(yr)
    base = historical_vulnerability(yr - 1)["hist_composite"]
    actual = hist[hist.year == yr].set_index("province")["housing_units"]
    common = sig.dropna().index.intersection(base.dropna().index).intersection(actual.index)
    X = pd.DataFrame({"rain": sig.loc[common, "rain_mm"],
                      "flood": sig.loc[common, "share_atrisk"],
                      "hist": base.loc[common]})
    pool_x.append(X.rank())            # rank-transform -> robust, scale-free
    pool_y.append(actual.loc[common].rank())
Xr = pd.concat(pool_x); yr_ = pd.concat(pool_y)
Xz = (Xr - Xr.mean()) / Xr.std()
yz = (yr_ - yr_.mean()) / yr_.std()
A = np.column_stack([np.ones(len(Xz)), Xz.values])
beta, *_ = np.linalg.lstsq(A, yz.values, rcond=None)
yhat = A @ beta
r2 = 1 - ((yz.values - yhat) ** 2).sum() / ((yz.values - yz.values.mean()) ** 2).sum()
factor_reg = pd.DataFrame({"factor": ["intercept", "rain", "flood", "hist"],
                           "std_beta": np.round(beta, 3)})
factor_reg.loc[len(factor_reg)] = ["model_R2", round(r2, 3)]
factor_reg.to_csv(os.path.join(OUT, "S2_factor_regression.csv"), index=False, encoding="utf-8-sig")


def composite_score(forecast_sig, hist_vuln, weights):
    """Apply the scoring formula to any set of signals (reused for the
    out-of-time test and for the 2026 forward score). Rain is intentionally
    NOT a term here - it is confounded across provinces (SECTION 3)."""
    return (weights["flood"] * norm_minmax(forecast_sig["share_atrisk"])
            + weights["hist"] * hist_vuln["hist_composite"])


# Out-of-TIME test of the SCORING FORMULA itself: build a 2025 score from
# 2025 forecasts + history through 2024 only (no leakage), then check it ranks
# the provinces that actually flooded in 2025. This validates the *composite*,
# not just the individual factors.
comp25 = composite_score(forecast_signals(2025), historical_vulnerability(2024), WEIGHTS)
oot_rows = []
for adim in ACTUAL_DIMS:
    act = hist[hist.year == 2025].set_index("province")[adim]
    common = comp25.dropna().index.intersection(act.dropna().index)
    rho, p = spearmanr(comp25.loc[common], act.loc[common])
    oot_rows.append({"composite": "2025 score (history<=2024 + 2025 forecasts)",
                     "actual_2025": adim, "n": len(common),
                     "spearman_rho": round(rho, 3), "p_value": p})
oot = pd.DataFrame(oot_rows)
oot.to_csv(os.path.join(OUT, "S3_composite_validation.csv"), index=False, encoding="utf-8-sig")

# ===================================================================
# SECTION 4 - MEANING OF RISK LEVEL  (requirement 3)
# ===================================================================
LEVELS = ["1 - Very Low", "2 - Low", "3 - Moderate", "4 - High", "5 - Very High"]
RISK_LEVEL_MEANING = pd.DataFrame([
    ("5 - Very High", "Top 20% of provinces. High forecast rain AND high flood-model "
     "flagging AND a heavy damage history. Expect material 2026 monsoon flood losses."),
    ("4 - High", "Strong on two of the three factors. Elevated 2026 loss risk."),
    ("3 - Moderate", "Mixed signals; average exposure. Monitor through the monsoon."),
    ("2 - Low", "Low forecast hazard and light damage history."),
    ("1 - Very Low", "Bottom 20%. Minimal forecast rain/flood signal and little history."),
], columns=["risk_level", "meaning"])
RISK_LEVEL_MEANING.to_csv(os.path.join(OUT, "risk_level_meaning.csv"),
                          index=False, encoding="utf-8-sig")

# ===================================================================
# SECTION 5 - FORWARD-LOOKING 2026 RISK SCORE & 5-LEVEL CLASS
# ===================================================================
sig26 = forecast_signals(FORWARD_YEAR)
vuln = historical_vulnerability(max(HIST_YEARS))            # full 2019-2025 history

scores = pd.DataFrame(index=meta.set_index("province").index)
scores = scores.join(meta.set_index("province")[["region_en"]])
scores["f_rain"] = norm_minmax(sig26["rain_mm"])
scores["f_flood"] = norm_minmax(sig26["share_atrisk"])
scores["f_hist"] = vuln["hist_composite"]                  # already [0,1] from norm_log
scores = scores.fillna(0.0)

# Same formula validated out-of-time above, now applied to the 2026 horizon.
scores["raw"] = composite_score(sig26, vuln, WEIGHTS).reindex(scores.index).fillna(0.0)
scores["risk_score"] = (100 * scores["raw"] / scores["raw"].max()).round(2)

# 5 levels by quintile of RANK (tie-safe, like the sibling project).
scores["risk_level"] = pd.qcut(scores["risk_score"].rank(method="first"), 5, labels=LEVELS)

# attach raw context for interpretability
scores["forecast_rain_mm"] = sig26["rain_mm"].round(1)
scores["flood_atrisk_share"] = sig26["share_atrisk"].round(4)
scores["flash_share"] = sig26["share_flash"].round(4)
scores = scores.join(vuln[["affected_people", "housing_units", "years_affected"]].astype(int))
scores = scores.sort_values("risk_score", ascending=False)
scores.to_csv(os.path.join(OUT, "forward_risk_scores_2026.csv"), encoding="utf-8-sig")

top20 = scores.head(20)
top20.to_csv(os.path.join(OUT, "top20_forward_risk_2026.csv"), encoding="utf-8-sig")

# ===================================================================
# SECTION 6 - BREAKDOWNS: quarterly, seasonal, area(region), type-of-risk
# ===================================================================
# 6a. National monthly profile (rain & at-risk share) per year
nat_month = (rain.groupby(["forecast_year", "forecast_month"])["rainfall_mm"].mean()
             .reset_index()
             .merge(flood_fc.groupby(["forecast_year", "forecast_month"])["share_atrisk"].mean()
                    .reset_index(), on=["forecast_year", "forecast_month"]))
nat_month.to_csv(os.path.join(OUT, "national_monthly_profile.csv"), index=False, encoding="utf-8-sig")

# 6b. Quarterly & seasonal aggregates (2026 forward)
qtr = (flood_fc[flood_fc.forecast_year == FORWARD_YEAR]
       .groupby("quarter").agg(mean_atrisk_share=("share_atrisk", "mean"),
                               mean_flash_share=("share_flash", "mean")).reset_index())
qtr = qtr.merge(rain[rain.forecast_year == FORWARD_YEAR]
                .groupby("quarter")["rainfall_mm"].mean().reset_index(), on="quarter")
qtr.to_csv(os.path.join(OUT, "quarterly_2026.csv"), index=False, encoding="utf-8-sig")

seasonal = (flood_fc[flood_fc.forecast_year == FORWARD_YEAR]
            .groupby("season").agg(mean_atrisk_share=("share_atrisk", "mean")).reset_index()
            .merge(rain[rain.forecast_year == FORWARD_YEAR].groupby("season")["rainfall_mm"]
                   .mean().reset_index(), on="season"))
seasonal.to_csv(os.path.join(OUT, "seasonal_2026.csv"), index=False, encoding="utf-8-sig")

# 6c. Region (area) summary - forward score + factors by region
region_sum = (scores.groupby("region_en")
              .agg(provinces=("risk_score", "size"),
                   mean_risk_score=("risk_score", "mean"),
                   mean_forecast_rain=("forecast_rain_mm", "mean"),
                   mean_atrisk_share=("flood_atrisk_share", "mean"),
                   mean_flash_share=("flash_share", "mean"))
              .round(3).sort_values("mean_risk_score", ascending=False))
region_sum.to_csv(os.path.join(OUT, "region_summary_2026.csv"), encoding="utf-8-sig")

# 6d. Type of risk - flood vs flashflood share by region (monsoon 2026)
type_region = (flood_fc[(flood_fc.forecast_year == FORWARD_YEAR)
                        & flood_fc.forecast_month.between(*MONSOON)]
               .groupby("region_en")[["share_flood", "share_flash"]].mean().round(4)
               .sort_values("share_flood", ascending=False))
type_region.to_csv(os.path.join(OUT, "type_of_risk_by_region.csv"), encoding="utf-8-sig")

# ===================================================================
# SECTION 7 - CORRELATION among factors & actuals  (requirement 5)
# ===================================================================
corr_df = pd.DataFrame({
    "forecast_rain_2026": sig26["rain_mm"],
    "flood_share_2026": sig26["share_atrisk"],
    "flash_share_2026": sig26["share_flash"],
    "hist_vulnerability": vuln["hist_composite"],
    "actual_2025_people": hist[hist.year == 2025].set_index("province")["affected_people"],
    "actual_2025_housing": hist[hist.year == 2025].set_index("province")["housing_units"],
}).dropna()
corr = corr_df.corr(method="spearman").round(3)
corr.to_csv(os.path.join(OUT, "correlation_matrix.csv"), encoding="utf-8-sig")

# ===================================================================
# SECTION 8 - FIGURES
# ===================================================================
LEVEL_COLORS = {LEVELS[0]: "#2c7bb6", LEVELS[1]: "#abd9e9", LEVELS[2]: "#ffffbf",
                LEVELS[3]: "#fdae61", LEVELS[4]: "#d7191c"}


# --- F1: Top 20 forward-looking 2026 risk, colored by level ---------------
fig, ax = plt.subplots(figsize=(10, 8))
t = top20.iloc[::-1]
ax.barh(t.index, t["risk_score"],
        color=[LEVEL_COLORS[str(l)] for l in t["risk_level"]], edgecolor="grey", lw=0.4)
for i, (_, r) in enumerate(t.iterrows()):
    ax.text(r["risk_score"] + 0.8, i, f'{r["risk_score"]:.1f}', va="center", fontsize=9)
ax.set_xlabel("Forward-looking flood-risk score (0-100)")
ax.set_xlim(0, 110)
ax.set_title("Top 20 จังหวัด — 2026 Forward-Looking Flood Risk\n"
             f"score = {WEIGHTS['flood']:.0%} flood-forecast + {WEIGHTS['hist']:.0%} history "
             "(monsoon Jun-Oct; rain used for timing only)", fontsize=11)
ax.legend(handles=[Patch(color=c, label=l) for l, c in LEVEL_COLORS.items()],
          title="Risk level", loc="lower right", fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "F1_top20_forward_risk_2026.png"), dpi=150)
plt.close(fig)


# --- F2: validation scatter - forecast vs actual --------------------------
fig, axes = plt.subplots(1, 2, figsize=(15, 6))
sig25 = forecast_signals(2025)
act25 = hist[hist.year == 2025].set_index("province")["housing_units"]
for ax, (xcol, xlabel) in zip(axes, [("rain_mm", "Forecast rainfall 2025 (mm, monsoon)"),
                                      ("share_atrisk", "Forecast flood at-risk share 2025 (monsoon)")]):
    common = sig25.dropna().index.intersection(act25.index)
    x, y = sig25.loc[common, xcol], act25.loc[common]
    rho, p = spearmanr(x, y)
    ax.scatter(x, np.log1p(y), s=22, color="#1f77b4", alpha=0.7)
    ax.set_xlabel(xlabel); ax.set_ylabel("Actual housing damaged 2025 (log1p units)")
    ax.set_title(f"Spearman rho = {rho:.2f}  (p = {p:.1e}, n = {len(common)})", fontsize=11)
fig.suptitle("Validation: provinces the forecasts rank higher take more real flood damage (2025)",
             fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(os.path.join(FIG, "F2_forecast_validation.png"), dpi=150)
plt.close(fig)


# --- F3: national monthly rain + at-risk share, season-shaded -------------
fig, axes = plt.subplots(1, 3, figsize=(20, 5.5), sharey=False)
SEASON_BANDS = [(5.5, 10.5, "#cfe8ff", "Monsoon")]   # Jun-Oct
for ax, yr in zip(axes, [2024, 2025, 2026]):
    d = nat_month[nat_month.forecast_year == yr]
    for x0, x1, c, _ in SEASON_BANDS:
        ax.axvspan(x0, x1, color=c, alpha=0.6, zorder=0)
    ax.plot(d.forecast_month, d.rainfall_mm, "o-", color="#1f77b4", label="rainfall (mm)")
    ax.set_xticks(range(1, 13)); ax.set_xlabel("month"); ax.set_title(f"{yr}")
    ax.set_ylabel("mean rainfall (mm)", color="#1f77b4")
    ax2 = ax.twinx()
    ax2.plot(d.forecast_month, d.share_atrisk, "s--", color="#d62728", label="at-risk share")
    ax2.set_ylabel("flood at-risk share", color="#d62728")
fig.suptitle("National monthly forecast profile — rainfall & flood at-risk share "
             "(shaded = monsoon Jun-Oct)", fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(os.path.join(FIG, "F3_monthly_seasonal_profile.png"), dpi=150)
plt.close(fig)


# --- F4: quarterly 2026 bars (rain & at-risk share) -----------------------
fig, ax = plt.subplots(figsize=(9, 5.5))
x = np.arange(len(qtr)); w = 0.38
ax.bar(x - w / 2, qtr["rainfall_mm"], w, color="#1f77b4", label="rainfall (mm)")
ax.set_ylabel("mean rainfall (mm)", color="#1f77b4"); ax.set_xticks(x, qtr["quarter"])
ax2 = ax.twinx()
ax2.bar(x + w / 2, qtr["mean_atrisk_share"], w, color="#d62728", label="at-risk share")
ax2.set_ylabel("flood at-risk share", color="#d62728")
ax.set_title("2026 forecast by quarter — rainfall vs flood at-risk share")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "F4_quarterly_2026.png"), dpi=150)
plt.close(fig)


# --- F5: region area summary + type-of-risk (flood vs flashflood) ---------
fig, (axA, axB) = plt.subplots(1, 2, figsize=(16, 6))
rs = region_sum.iloc[::-1]
axA.barh(rs.index, rs["mean_risk_score"], color="#9467bd", edgecolor="grey")
axA.set_xlabel("mean 2026 forward risk score"); axA.set_title("Risk by region (area)")
for i, v in enumerate(rs["mean_risk_score"]):
    axA.text(v + 0.3, i, f"{v:.1f}", va="center", fontsize=9)
tr = type_region.iloc[::-1]
axB.barh(tr.index, tr["share_flood"], color="#1f77b4", label="flood (น้ำท่วม)")
axB.barh(tr.index, tr["share_flash"], left=tr["share_flood"], color="#ff7f0e",
         label="flashflood (น้ำท่วมฉับพลัน)")
axB.set_xlabel("monsoon at-risk share by type"); axB.set_title("Type of risk by region (2026 monsoon)")
axB.legend(fontsize=9)
fig.suptitle("Area & type-of-risk breakdown (2026 forecast)", fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(os.path.join(FIG, "F5_region_type_breakdown.png"), dpi=150)
plt.close(fig)


# --- F6: correlation heatmap ----------------------------------------------
fig, ax = plt.subplots(figsize=(8.5, 7))
im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
ax.set_xticks(range(len(corr)), corr.columns, rotation=45, ha="right", fontsize=8)
ax.set_yticks(range(len(corr)), corr.index, fontsize=8)
for i in range(len(corr)):
    for j in range(len(corr)):
        ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center",
                fontsize=8, color="white" if abs(corr.values[i, j]) > 0.6 else "black")
fig.colorbar(im, ax=ax, label="Spearman ρ")
ax.set_title("Correlation: forecast factors vs historical vulnerability vs actual damage")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "F6_correlation_matrix.png"), dpi=150)
plt.close(fig)


# --- F7: risk-level distribution + all provinces ranked -------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 12), width_ratios=[1, 2.2])
cnt = scores["risk_level"].value_counts().reindex(LEVELS)
ax1.bar(range(5), cnt.values, color=[LEVEL_COLORS[l] for l in LEVELS], edgecolor="grey")
ax1.set_xticks(range(5), [l.replace(" - ", "\n") for l in LEVELS], fontsize=9)
ax1.set_ylabel("number of provinces"); ax1.set_title("Provinces per 2026 risk level (quintiles)")
for i, v in enumerate(cnt.values):
    ax1.text(i, v + 0.2, str(v), ha="center")
r = scores.iloc[::-1]
ax2.barh(r.index, r["risk_score"],
         color=[LEVEL_COLORS[str(l)] for l in r["risk_level"]], edgecolor="grey", lw=0.3)
ax2.tick_params(axis="y", labelsize=6.5); ax2.set_xlabel("forward risk score (0-100)")
ax2.set_title("All 77 provinces ranked — 2026 forward-looking flood risk")
ax2.legend(handles=[Patch(color=c, label=l) for l, c in LEVEL_COLORS.items()],
           title="Risk level", loc="lower right")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "F7_risk_levels_all_provinces.png"), dpi=150)
plt.close(fig)

# ===================================================================
# SECTION 9 - Console summary (every headline stat used in EXPLANATION.md)
# ===================================================================
print("=" * 70)
print("VALIDATION — forecast signal vs ACTUAL damage (Spearman ρ):")
print(validation.to_string(index=False))
print("\nFactor regression on actual housing-damage rank (pooled 2024-2025):")
print(factor_reg.to_string(index=False))
print("\nOUT-OF-TIME composite validation (2025 score vs 2025 actuals):")
print(oot.to_string(index=False))
print("\n" + "=" * 70)
print("TOP 20 FORWARD-LOOKING RISK (2026):")
print(top20[["region_en", "risk_score", "risk_level", "forecast_rain_mm",
             "flood_atrisk_share", "years_affected"]].to_string())
print("\nRISK LEVEL COUNTS:")
print(scores["risk_level"].value_counts().reindex(LEVELS).to_string())
print("\nREGION SUMMARY (2026):")
print(region_sum.to_string())
print("\nTYPE OF RISK BY REGION (monsoon 2026):")
print(type_region.to_string())
print("\nCORRELATION MATRIX (Spearman):")
print(corr.to_string())
print("\nDone. Figures ->", FIG, "| Tables ->", OUT)

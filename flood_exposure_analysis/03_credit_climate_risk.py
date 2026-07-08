"""
03_credit_climate_risk.py
Climate (flood) exposure as a credit-risk overlay for three consumer-credit
portfolios: Mortgage, Business/SME loans (unlisted companies), Automobile (HP).

Every headline claim is backed by a statistic computed here:
  S1  Dimension correlation structure (Spearman) - justifies grouping
  S2  PCA validation - shows rankings are not an artifact of chosen weights
  S3  Mann-Kendall + Theil-Sen trend tests - is exposure growing?
  S4  Persistence tests - does past exposure predict future exposure?
  S5  Concentration (Gini / Lorenz / top-share) - portfolio concentration risk
  S6  Weight sensitivity analysis - are the top-20 lists robust?

Inputs : data/province_year.csv (from 01_clean_prepare.py)
Outputs: output/credit/*.csv, figures/credit/*.png
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.decomposition import PCA

BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures", "credit")
OUTT = os.path.join(BASE, "output", "credit")
os.makedirs(FIG, exist_ok=True)
os.makedirs(OUTT, exist_ok=True)

plt.rcParams["font.family"] = "Thonburi"
plt.rcParams["axes.unicode_minus"] = False

RNG = np.random.default_rng(42)

pv = pd.read_csv(os.path.join(BASE, "data", "province_year.csv"))
YEARS = sorted(pv.year.unique())
N_YEARS = len(YEARS)

DIMS = ["affected_people", "affected_households", "evacuated_people", "deaths",
        "injured", "housing_units", "business_sites", "agriculture_rai",
        "livestock_head", "fisheries_units", "transport_sites",
        "infrastructure_sites"]
DIM_LABELS = {
    "affected_people": "Affected people", "affected_households": "Affected households",
    "evacuated_people": "Evacuated people", "deaths": "Deaths", "injured": "Injured",
    "housing_units": "Housing damaged", "business_sites": "Business sites",
    "agriculture_rai": "Agriculture (rai)", "livestock_head": "Livestock",
    "fisheries_units": "Fisheries", "transport_sites": "Transport/roads",
    "infrastructure_sites": "Infrastructure sites"}

agg = pv.groupby("province")[DIMS].sum(min_count=1).fillna(0)
agg["years_affected"] = pv[pv[["affected_people", "villages_affected", "housing_units"]]
                           .fillna(0).sum(axis=1) > 0].groupby("province")["year"].nunique()
agg["years_affected"] = agg["years_affected"].fillna(0)
freq = agg["years_affected"] / N_YEARS


def norm(s):
    s = np.log1p(s.astype(float))
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng > 0 else s * 0


nrm = pd.DataFrame({c: norm(agg[c]) for c in DIMS})

# ============================================================================
# S1) Correlation structure between dimensions (Spearman, province aggregates)
# ============================================================================
corr = agg[DIMS].corr(method="spearman")
corr.round(3).to_csv(os.path.join(OUTT, "S1_dimension_spearman_corr.csv"),
                     encoding="utf-8-sig")

# ============================================================================
# S2) PCA on normalized dimensions - benchmark ranking independent of weights
# ============================================================================
pca = PCA(n_components=3)
pcs = pca.fit_transform(nrm.values)
pc1 = pd.Series(pcs[:, 0], index=agg.index)
if pca.components_[0].sum() < 0:          # orient PC1 so higher = more exposed
    pc1 = -pc1
    pca.components_[0] *= -1              # keep saved loadings consistent with pc1
pc1_var = pca.explained_variance_ratio_[0]
loadings = pd.DataFrame(pca.components_.T, index=DIMS,
                        columns=["PC1", "PC2", "PC3"])
loadings.round(3).to_csv(os.path.join(OUTT, "S2_pca_loadings.csv"),
                         encoding="utf-8-sig")

PORTFOLIOS = {
    "mortgage": {
        "collateral_damage":  (["housing_units"], 0.35),   # direct damage to mortgaged property
        "borrower_disruption": (["affected_households"], 0.25),  # income/payment interruption
        "habitability_loss":  (["evacuated_people"], 0.10),      # severity of displacement
        "area_recoverability": (["transport_sites", "infrastructure_sites"], 0.10),
        "recurrence":         ("FREQ", 0.20),              # chronic flooding -> value decline, insurance retreat
    },
    "business_sme": {
        "business_interruption": (["business_sites"], 0.30),
        "agri_sme_exposure":  (["agriculture_rai", "livestock_head", "fisheries_units"], 0.25),
        "supply_chain":       (["transport_sites", "infrastructure_sites"], 0.15),
        "local_demand_shock": (["affected_people"], 0.10),
        "recurrence":         ("FREQ", 0.20),
    },
    "automobile": {
        "vehicle_damage_proxy": (["housing_units"], 0.25),  # vehicles flood where homes flood
        "owner_base_affected": (["affected_households"], 0.25),
        "sudden_onset":       (["evacuated_people"], 0.15),  # no time to relocate vehicles
        "road_disruption":    (["transport_sites"], 0.15),   # usage, valuation, repossession logistics
        "recurrence":         ("FREQ", 0.20),
    },
}


def build_score(spec, nrm_df=nrm, freq_s=freq):
    score = pd.Series(0.0, index=nrm_df.index)
    comps = pd.DataFrame(index=nrm_df.index)
    for cname, (cols, w) in spec.items():
        comp = freq_s if isinstance(cols, str) else nrm_df[cols].mean(axis=1)
        comps[cname] = comp
        score = score + w * comp
    return 100 * score / score.max(), comps


labels5 = ["1 - Very Low", "2 - Low", "3 - Moderate", "4 - High", "5 - Very High"]
scores, all_comps = {}, {}
for pname, spec in PORTFOLIOS.items():
    s, comps = build_score(spec)
    scores[pname] = s
    all_comps[pname] = comps

risk = pd.DataFrame({f"{p}_score": s.round(2) for p, s in scores.items()})
for p in PORTFOLIOS:
    risk[f"{p}_level"] = pd.qcut(risk[f"{p}_score"].rank(method="first"),
                                 5, labels=labels5)
risk = risk.join(agg[["years_affected", "affected_people", "affected_households",
                      "housing_units", "business_sites", "agriculture_rai",
                      "transport_sites"]].astype(int))
risk = risk.sort_values("mortgage_score", ascending=False)
risk.to_csv(os.path.join(OUTT, "credit_portfolio_scores.csv"), encoding="utf-8-sig")

# S2 validation: agreement of each portfolio score with the PCA benchmark
pca_val = []
for p, s in scores.items():
    rho, pval = stats.spearmanr(s, pc1)
    top20_overlap = len(set(s.nlargest(20).index) & set(pc1.nlargest(20).index))
    pca_val.append({"portfolio": p, "spearman_vs_PC1": round(rho, 3),
                    "p_value": pval, "top20_overlap_with_PC1": top20_overlap})
pca_val = pd.DataFrame(pca_val)
pca_val.to_csv(os.path.join(OUTT, "S2_pca_validation.csv"),
               index=False, encoding="utf-8-sig")

# ============================================================================
# S3) Trend tests on national yearly totals: Mann-Kendall (via Kendall tau on
#     time) + Theil-Sen slope (robust) + OLS for reference. n=7 years -> low
#     power; p-values reported as-is, no cherry-picking.
# ============================================================================
nat = pv.groupby("year")[DIMS].sum(min_count=1)
x = np.array(YEARS, dtype=float)
trend_rows = []
for d in DIMS:
    y = nat[d].astype(float).values
    tau, p_mk = stats.kendalltau(x, y)
    ts = stats.theilslopes(y, x)
    ols = stats.linregress(x, y)
    trend_rows.append({
        "dimension": d, "kendall_tau": round(tau, 3), "mk_p_value": round(p_mk, 4),
        "theil_sen_slope_per_year": round(ts.slope, 1),
        "ols_slope_per_year": round(ols.slope, 1),
        "ols_r2": round(ols.rvalue ** 2, 3), "ols_p_value": round(ols.pvalue, 4),
        "mean_level": round(np.mean(y), 1),
        "sen_slope_pct_of_mean": round(100 * ts.slope / np.mean(y), 1)})
trend = pd.DataFrame(trend_rows)
trend.to_csv(os.path.join(OUTT, "S3_trend_tests.csv"),
             index=False, encoding="utf-8-sig")

# ============================================================================
# S4) Persistence: does province exposure in year t predict year t+1?
#     (a) consecutive-year Spearman rank correlation
#     (b) top-quintile retention vs 20% base rate (exact binomial test)
# ============================================================================
PERSIST_DIMS = ["affected_people", "affected_households", "housing_units"]
persist_rows, retention = [], {}
for d in PERSIST_DIMS:
    wide = pv.pivot_table(index="province", columns="year", values=d,
                          aggfunc="sum").fillna(0)
    hits, trials, rhos = 0, 0, []
    for y0, y1 in zip(YEARS[:-1], YEARS[1:]):
        a, b = wide[y0], wide[y1]
        rho, pval = stats.spearmanr(a, b)
        rhos.append(rho)
        persist_rows.append({"dimension": d, "year_pair": f"{y0}->{y1}",
                             "spearman_rho": round(rho, 3), "p_value": pval})
        k = max(1, int(np.ceil(0.20 * len(a))))
        top0 = set(a.nlargest(k).index)
        top1 = set(b.nlargest(k).index)
        hits += len(top0 & top1)
        trials += k
    btest = stats.binomtest(hits, trials, p=0.20, alternative="greater")
    retention[d] = {"dimension": d, "mean_lag1_spearman": round(np.mean(rhos), 3),
                    "top_quintile_retention": round(hits / trials, 3),
                    "base_rate": 0.20, "binom_p_value": btest.pvalue,
                    "hits": hits, "trials": trials}
persist = pd.DataFrame(persist_rows)
persist.to_csv(os.path.join(OUTT, "S4_persistence_by_yearpair.csv"),
               index=False, encoding="utf-8-sig")
retention = pd.DataFrame(retention.values())
retention.to_csv(os.path.join(OUTT, "S4_persistence_summary.csv"),
                 index=False, encoding="utf-8-sig")

# ============================================================================
# S5) Concentration of exposure across provinces: Gini, Lorenz, top shares
# ============================================================================


def gini(v):
    v = np.sort(np.asarray(v, dtype=float))
    n = len(v)
    if v.sum() == 0:
        return 0.0
    return float((2 * np.arange(1, n + 1) - n - 1).dot(v) / (n * v.sum()))


CONC_DIMS = ["affected_people", "housing_units", "business_sites", "agriculture_rai"]
conc_rows = []
for d in CONC_DIMS:
    v = agg[d]
    top10 = v.nlargest(10).sum() / v.sum()
    top20 = v.nlargest(20).sum() / v.sum()
    conc_rows.append({"dimension": d, "gini": round(gini(v), 3),
                      "top10_province_share": round(top10, 3),
                      "top20_province_share": round(top20, 3)})
conc = pd.DataFrame(conc_rows)
conc.to_csv(os.path.join(OUTT, "S5_concentration.csv"),
            index=False, encoding="utf-8-sig")

# ============================================================================
# S6) Weight sensitivity: perturb each weight by U(0.5, 1.5), renormalize,
#     rebuild score 2,000x. Report top-20 overlap and rank correlation with
#     the baseline -> shows conclusions are not driven by the chosen weights.
# ============================================================================
N_SIM = 2000
sens_rows, sens_overlaps = [], {}
for pname, spec in PORTFOLIOS.items():
    base = scores[pname]
    base_top = set(base.nlargest(20).index)
    overlaps, rhos = [], []
    keys = list(spec.keys())
    w0 = np.array([spec[k][1] for k in keys])
    comps = all_comps[pname]
    for _ in range(N_SIM):
        w = w0 * RNG.uniform(0.5, 1.5, size=len(w0))
        w = w / w.sum()
        s = comps[keys].values @ w
        s = pd.Series(s, index=comps.index)
        overlaps.append(len(set(s.nlargest(20).index) & base_top))
        rhos.append(stats.spearmanr(s, base)[0])
    overlaps, rhos = np.array(overlaps), np.array(rhos)
    sens_overlaps[pname] = overlaps
    sens_rows.append({"portfolio": pname, "n_sim": N_SIM,
                      "mean_top20_overlap": round(overlaps.mean(), 2),
                      "p5_top20_overlap": int(np.percentile(overlaps, 5)),
                      "min_top20_overlap": int(overlaps.min()),
                      "mean_rank_spearman": round(rhos.mean(), 4),
                      "p5_rank_spearman": round(np.percentile(rhos, 5), 4)})
sens = pd.DataFrame(sens_rows)
sens.to_csv(os.path.join(OUTT, "S6_weight_sensitivity.csv"),
            index=False, encoding="utf-8-sig")

# ============================================================================
# Projections 2026-2028 for credit-relevant dimensions (OLS + Theil-Sen),
# honest uncertainty band (+-1 SE of OLS residuals)
# ============================================================================
CREDIT_TREND_DIMS = ["housing_units", "business_sites",
                     "agriculture_rai", "affected_households"]
proj_years = np.array([2026, 2027, 2028], dtype=float)
proj_rows = []
for d in CREDIT_TREND_DIMS:
    y = nat[d].astype(float).values
    ols = stats.linregress(x, y)
    ts = stats.theilslopes(y, x)
    resid = y - (ols.intercept + ols.slope * x)
    se = resid.std(ddof=2)
    for py in proj_years:
        p_ols = max(ols.intercept + ols.slope * py, 0)
        p_ts = max(ts.intercept + ts.slope * py, 0)
        proj_rows.append({"dimension": d, "year": int(py),
                          "ols_projection": round(p_ols, 0),
                          "theil_sen_projection": round(p_ts, 0),
                          "lower(~68%)": round(max(p_ols - se, 0), 0),
                          "upper(~68%)": round(p_ols + se, 0)})
proj = pd.DataFrame(proj_rows)
proj.to_csv(os.path.join(OUTT, "credit_projection_2026_2028.csv"),
            index=False, encoding="utf-8-sig")

# ============================================================================
# Figures
# ============================================================================
LEVEL_COLORS = {labels5[0]: "#2c7bb6", labels5[1]: "#abd9e9", labels5[2]: "#ffffbf",
                labels5[3]: "#fdae61", labels5[4]: "#d7191c"}
PORTFOLIO_TITLES = {"mortgage": "Mortgage portfolio",
                    "business_sme": "Business/SME loans (unlisted)",
                    "automobile": "Automobile / HP portfolio"}

# C1: top-20 provinces per portfolio
fig, axes = plt.subplots(1, 3, figsize=(22, 9))
for ax, p in zip(axes, PORTFOLIOS):
    t = risk.sort_values(f"{p}_score", ascending=False).head(20).iloc[::-1]
    ax.barh(t.index, t[f"{p}_score"],
            color=[LEVEL_COLORS[str(l)] for l in t[f"{p}_level"]],
            edgecolor="grey", lw=0.4)
    for i, (_, r) in enumerate(t.iterrows()):
        ax.text(r[f"{p}_score"] + 0.8, i, f'{r[f"{p}_score"]:.1f}',
                va="center", fontsize=8)
    ax.set_title(PORTFOLIO_TITLES[p], fontsize=12)
    ax.set_xlabel("Flood exposure score (0-100)")
    ax.set_xlim(0, 112)
    ax.tick_params(labelsize=9)
fig.suptitle("Top 20 provinces by portfolio-specific flood exposure score "
             "(2019-2025, DDPM data)", fontsize=14)
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(os.path.join(FIG, "C1_top20_by_portfolio.png"), dpi=150)
plt.close(fig)

# C2: Lorenz curves (concentration)
fig, ax = plt.subplots(figsize=(8, 8))
for d in CONC_DIMS:
    v = np.sort(agg[d].values)
    cum = np.insert(np.cumsum(v) / v.sum(), 0, 0)
    pop = np.linspace(0, 1, len(cum))
    g = conc.loc[conc.dimension == d, "gini"].iloc[0]
    ax.plot(pop, cum, label=f"{DIM_LABELS[d]} (Gini={g:.2f})", lw=2)
ax.plot([0, 1], [0, 1], "k--", lw=1, label="Perfect equality")
ax.set_xlabel("Cumulative share of provinces")
ax.set_ylabel("Cumulative share of flood exposure")
ax.set_title("Lorenz curves: flood exposure is highly concentrated\n"
             "in a minority of provinces (2019-2025 cumulative)")
ax.legend(fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "C2_lorenz_concentration.png"), dpi=150)
plt.close(fig)

# C3: trends + projections for credit-relevant dimensions
fig, axes = plt.subplots(2, 2, figsize=(15, 10))
for ax, d in zip(axes.flat, CREDIT_TREND_DIMS):
    y = nat[d].astype(float).values
    ols = stats.linregress(x, y)
    ts = stats.theilslopes(y, x)
    tau, p_mk = stats.kendalltau(x, y)
    resid = y - (ols.intercept + ols.slope * x)
    se = resid.std(ddof=2)
    xx = np.r_[x, proj_years]
    ax.plot(x, y, "o-", color="#1f77b4", label="actual")
    ax.plot(xx, np.clip(ols.intercept + ols.slope * xx, 0, None), "--",
            color="grey", lw=1.2, label="OLS trend")
    ax.plot(xx, np.clip(ts.intercept + ts.slope * xx, 0, None), "-.",
            color="#2ca02c", lw=1.2, label="Theil-Sen (robust)")
    yp = np.clip(ols.intercept + ols.slope * proj_years, 0, None)
    ax.fill_between(proj_years, np.clip(yp - se, 0, None), yp + se,
                    color="#d62728", alpha=0.15)
    ax.plot(proj_years, yp, "s--", color="#d62728", label="projection")
    ax.axvline(2025.5, color="k", lw=0.5, ls=":")
    ax.set_title(f"{DIM_LABELS[d]}\nKendall tau={tau:.2f} (p={p_mk:.3f}), "
                 f"OLS R2={ols.rvalue**2:.2f} (p={ols.pvalue:.3f})", fontsize=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda v, _: f"{v/1e6:.1f}M" if v >= 1e6 else (f"{v/1e3:.0f}K" if v >= 1e3 else f"{v:.0f}")))
axes.flat[0].legend(fontsize=8)
fig.suptitle("Credit-relevant flood exposure trends 2019-2025, projected to 2028\n"
             "(n=7 years; shaded band = +-1 SE; volatile series - trend indication only)",
             fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig(os.path.join(FIG, "C3_credit_trends_projection.png"), dpi=150)
plt.close(fig)

# C4: persistence evidence
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
for d in PERSIST_DIMS:
    sub = persist[persist.dimension == d]
    ax1.plot(range(len(sub)), sub["spearman_rho"], "o-", label=DIM_LABELS[d])
ax1.set_xticks(range(N_YEARS - 1),
               [f"{a}\n->{b}" for a, b in zip(YEARS[:-1], YEARS[1:])], fontsize=8)
ax1.axhline(0, color="k", lw=0.5)
ax1.set_ylabel("Spearman rank correlation (year t vs t+1)")
ax1.set_title("Province flood ranking persists year over year")
ax1.legend(fontsize=9)
ax1.set_ylim(-0.1, 1)

bars = retention.set_index("dimension")["top_quintile_retention"]
ax2.bar([DIM_LABELS[d] for d in bars.index], bars.values, color="#1f77b4")
ax2.axhline(0.20, color="#d62728", ls="--", label="Base rate if random (20%)")
for i, v in enumerate(bars.values):
    ax2.text(i, v + 0.01, f"{v:.0%}", ha="center")
ax2.set_ylabel("P(top-quintile in year t+1 | top-quintile in year t)")
ax2.set_title("Top-quintile retention vs 20% random base rate\n"
              f"(largest binomial p-value = {retention['binom_p_value'].max():.1e})")
ax2.legend()
fig.tight_layout()
fig.savefig(os.path.join(FIG, "C4_persistence.png"), dpi=150)
plt.close(fig)

# C5: weight-sensitivity histograms (same draws as the S6 CSV)
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
for ax, pname in zip(axes, PORTFOLIOS):
    ovl = sens_overlaps[pname]
    ax.hist(ovl, bins=np.arange(min(ovl.min(), 14) - 0.5, 21.5),
            color="#1f77b4", edgecolor="white")
    ax.set_title(f"{PORTFOLIO_TITLES[pname]}\nmean overlap "
                 f"{ovl.mean():.1f}/20", fontsize=10)
    ax.set_xlabel("Top-20 provinces unchanged (out of 20)")
fig.suptitle(f"Weight sensitivity: each weight perturbed +-50%, {N_SIM:,} draws - "
             "top-20 lists barely move", fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.92])
fig.savefig(os.path.join(FIG, "C5_weight_sensitivity.png"), dpi=150)
plt.close(fig)

# C6: dimension correlation heatmap
fig, ax = plt.subplots(figsize=(10, 8.5))
im = ax.imshow(corr.values, cmap="RdYlBu_r", vmin=-1, vmax=1)
ax.set_xticks(range(len(DIMS)), [DIM_LABELS[d] for d in DIMS],
              rotation=45, ha="right", fontsize=8)
ax.set_yticks(range(len(DIMS)), [DIM_LABELS[d] for d in DIMS], fontsize=8)
for i in range(len(DIMS)):
    for j in range(len(DIMS)):
        ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center",
                fontsize=7, color="black")
fig.colorbar(im, ax=ax, label="Spearman rho")
ax.set_title("Spearman correlation between exposure dimensions\n"
             "(province cumulative totals 2019-2025)")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "C6_dimension_correlation.png"), dpi=150)
plt.close(fig)

# ============================================================================
# Console summary
# ============================================================================
print("=== S2 PCA: PC1 explains {:.1%} of variance ===".format(pc1_var))
print(pca_val.to_string(index=False))
print("\n=== TOP 10 PER PORTFOLIO ===")
for p in PORTFOLIOS:
    top = risk.sort_values(f"{p}_score", ascending=False).head(10)
    print(f"\n[{PORTFOLIO_TITLES[p]}]")
    print(top[[f"{p}_score", f"{p}_level"]].to_string())
print("\n=== S3 TREND TESTS (national yearly totals, n=7) ===")
print(trend.to_string(index=False))
print("\n=== S4 PERSISTENCE SUMMARY ===")
print(retention.to_string(index=False))
print("\n=== S5 CONCENTRATION ===")
print(conc.to_string(index=False))
print("\n=== S6 WEIGHT SENSITIVITY ===")
print(sens.to_string(index=False))
print("\n=== PROJECTIONS (credit dimensions) ===")
print(proj.to_string(index=False))
print("\nDone. Outputs ->", OUTT, "| Figures ->", FIG)

# ============================================================================
# Portfolio-specific exposure scores
# ----------------------------------------------------------------------------
# Weights encode the credit transmission channel for each portfolio
# (collateral damage, borrower income disruption, business interruption,
# recurrence). They are expert-judgment based and are VALIDATED below by
# (a) Spearman agreement with the weight-free PCA benchmark (S2) and
# (b) a 2,000-draw weight-perturbation sensitivity analysis (S6).
# Each entry: component -> (columns averaged after log1p min-max norm, weight)
# ============================================================================
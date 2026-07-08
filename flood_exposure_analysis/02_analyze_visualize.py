import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")
OUTT = os.path.join(BASE, "output")
os.makedirs(FIG, exist_ok=True)
os.makedirs(OUTT, exist_ok=True)

plt.rcParams["font.family"] = "Thonburi"
plt.rcParams["axes.unicode_minus"] = False

pv = pd.read_csv(os.path.join(BASE, "data", "province_year.csv"))
dv = pd.read_csv(os.path.join(BASE, "data", "district_year.csv"))

YEARS = sorted(pv.year.unique())
DIM_LABELS = {
    "affected_people": "Affected people (คน)",
    "affected_households": "Affected households (ครัวเรือน)",
    "evacuated_people": "Evacuated people (คน)",
    "deaths": "Deaths (คน)",
    "injured": "Injured (คน)",
    "housing_units": "Housing damaged (หลัง)",
    "business_sites": "Business sites (แห่ง)",
    "agriculture_rai": "Agriculture (ไร่)",
    "livestock_head": "Livestock (ตัว)",
    "fisheries_units": "Fisheries (บ่อ/กระชัง)",
    "transport_sites": "Transport/roads (แห่ง)",
    "infrastructure_sites": "Infrastructure & public sites (แห่ง)",
    "villages_affected": "Villages affected (หมู่บ้าน)",
    "subdistricts_affected": "Subdistricts affected (ตำบล)",
    "districts_affected": "Districts affected (อำเภอ)",
}
DIMS = list(DIM_LABELS)

# ============================================================================
# 1) Composite exposure score & 5-level risk classification (province)
# ============================================================================
agg = pv.groupby("province")[DIMS].sum(min_count=1).fillna(0)
agg["years_affected"] = pv[pv[["affected_people", "villages_affected", "housing_units"]]
                           .fillna(0).sum(axis=1) > 0].groupby("province")["year"].nunique()
agg["years_affected"] = agg["years_affected"].fillna(0)


def norm(s):
    s = np.log1p(s.astype(float))
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng > 0 else s * 0


components = {
    "human_impact":   (["affected_people", "affected_households"], 0.30),
    "life_safety":    (["deaths", "injured", "evacuated_people"], 0.20),
    "property":       (["housing_units", "business_sites"], 0.20),
    "agriculture":    (["agriculture_rai", "livestock_head", "fisheries_units"], 0.10),
    "infrastructure": (["transport_sites", "infrastructure_sites"], 0.10),
}
score = pd.Series(0.0, index=agg.index)
comp_df = pd.DataFrame(index=agg.index)
for name, (cols, w) in components.items():
    comp = pd.concat([norm(agg[c]) for c in cols], axis=1).mean(axis=1)
    comp_df[name] = comp
    score += w * comp
freq = agg["years_affected"] / len(YEARS)
comp_df["frequency"] = freq
score += 0.10 * freq
score = 100 * score / score.max()

risk = pd.DataFrame({"exposure_score": score.round(2)}).join(comp_df.round(3)).join(
    agg[["years_affected", "affected_people", "affected_households", "housing_units",
         "agriculture_rai", "deaths"]].astype(int))
# 5 risk levels by quintile of score
labels5 = ["1 - Very Low", "2 - Low", "3 - Moderate", "4 - High", "5 - Very High"]
risk["risk_level"] = pd.qcut(risk["exposure_score"], 5, labels=labels5)
risk = risk.sort_values("exposure_score", ascending=False)
risk.to_csv(os.path.join(OUTT, "province_risk_levels.csv"), encoding="utf-8-sig")

# ============================================================================
# 2) Top-20
# ============================================================================
top20 = risk.head(20)
top20.to_csv(os.path.join(OUTT, "top20_provinces_composite.csv"), encoding="utf-8-sig")

per_dim = {}
for d in ["affected_people", "affected_households", "housing_units", "agriculture_rai",
          "deaths", "evacuated_people", "livestock_head", "transport_sites"]:
    per_dim[d] = agg[d].sort_values(ascending=False).head(20)
pd.concat({k: v.reset_index().rename(columns={k: "value"}) for k, v in per_dim.items()},
          axis=1).to_csv(os.path.join(OUTT, "top20_provinces_by_dimension.csv"),
                         encoding="utf-8-sig", index=False)

dist = dv.groupby(["province", "district"]).agg(
    years=("year", "nunique"), events=("events", "sum"),
    affected_people=("affected_people", "sum"), affected_households=("affected_households", "sum"),
    housing_units=("housing_units", "sum"), agriculture_rai=("agriculture_rai", "sum"),
    deaths=("deaths", "sum")).sort_values("affected_people", ascending=False)
dist.head(20).to_csv(os.path.join(OUTT, "top20_districts.csv"), encoding="utf-8-sig")

# ============================================================================
# 3) Figures
# ============================================================================
LEVEL_COLORS = {labels5[0]: "#2c7bb6", labels5[1]: "#abd9e9", labels5[2]: "#ffffbf",
                labels5[3]: "#fdae61", labels5[4]: "#d7191c"}

# --- 3.1 Top 20 provinces by composite score, colored by risk level
fig, ax = plt.subplots(figsize=(10, 8))
t = top20.iloc[::-1]
ax.barh(t.index, t["exposure_score"],
        color=[LEVEL_COLORS[str(l)] for l in t["risk_level"]], edgecolor="grey", lw=0.4)
for i, (idx, r) in enumerate(t.iterrows()):
    ax.text(r["exposure_score"] + 0.8, i, f'{r["exposure_score"]:.1f}', va="center", fontsize=9)
ax.set_xlabel("Composite flood exposure score (0-100)")
ax.set_title("Top 20 จังหวัด — Flood Exposure Composite Score (2019-2025)\n"
             "weights: human 30% · life-safety 20% · property 20% · agri 10% · infra 10% · frequency 10%",
             fontsize=11)
ax.set_xlim(0, 110)
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in LEVEL_COLORS.values()]
ax.legend(handles, LEVEL_COLORS.keys(), title="Risk level", loc="lower right", fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "1_top20_provinces_composite.png"), dpi=150)
plt.close(fig)

# --- 3.2 Top 20 by each major dimension (8 panels)
fig, axes = plt.subplots(2, 4, figsize=(22, 10))
for ax, (d, s) in zip(axes.flat, per_dim.items()):
    s = s.iloc[::-1]
    ax.barh(s.index, s.values, color="#1f77b4")
    ax.set_title(DIM_LABELS[d], fontsize=11)
    ax.tick_params(labelsize=8)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(
        lambda x, _: f"{x/1e6:.1f}M" if x >= 1e6 else (f"{x/1e3:.0f}K" if x >= 1e3 else f"{x:.0f}")))
fig.suptitle("Top 20 จังหวัด by exposure dimension — cumulative 2019-2025", fontsize=14, y=1.0)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "2_top20_by_dimension.png"), dpi=150)
plt.close(fig)

# --- 3.3 Top 20 districts
fig, ax = plt.subplots(figsize=(10, 8))
td = dist.head(20).iloc[::-1]
lbl = [f"{d} ({p})" for p, d in td.index]
ax.barh(lbl, td["affected_people"], color="#d95f02")
ax.set_xlabel("Affected people, cumulative 2020-2024 (district detail years)")
ax.set_title("Top 20 อำเภอ — Flood-affected people")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/1e3:.0f}K"))
fig.tight_layout()
fig.savefig(os.path.join(FIG, "3_top20_districts.png"), dpi=150)
plt.close(fig)

# ============================================================================
# 4) Yearly national exposure + projection to 2028
# ============================================================================
nat = pv.groupby("year")[DIMS].sum(min_count=1)
proj_years = np.array([2026, 2027, 2028])
proj_rows = []
fig, axes = plt.subplots(3, 4, figsize=(20, 12))
plot_dims = ["affected_people", "affected_households", "evacuated_people", "deaths",
             "injured", "housing_units", "business_sites", "agriculture_rai",
             "livestock_head", "fisheries_units", "transport_sites", "infrastructure_sites"]
for ax, d in zip(axes.flat, plot_dims):
    y = nat[d].astype(float)
    x = np.array(YEARS, dtype=float)
    b, a = np.polyfit(x, y.values, 1)                 # linear OLS trend
    resid = y.values - (a + b * x)
    se = resid.std(ddof=2)
    yp = a + b * proj_years
    yp = np.clip(yp, 0, None)
    for py, pval in zip(proj_years, yp):
        proj_rows.append({"dimension": d, "year": py, "projected": round(float(pval), 0),
                          "lower(~68%)": round(max(float(pval - se), 0), 0),
                          "upper(~68%)": round(float(pval + se), 0)})
    ax.plot(x, y.values, "o-", color="#1f77b4", label="actual")
    xx = np.r_[x, proj_years]
    ax.plot(xx, np.clip(a + b * xx, 0, None), "--", color="grey", lw=1, label="trend")
    ax.plot(proj_years, yp, "s--", color="#d62728", label="projection")
    ax.fill_between(proj_years, np.clip(yp - se, 0, None), yp + se, color="#d62728", alpha=0.15)
    ax.set_title(DIM_LABELS[d], fontsize=11)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda v, _: f"{v/1e6:.1f}M" if v >= 1e6 else (f"{v/1e3:.0f}K" if v >= 1e3 else f"{v:.0f}")))
    ax.tick_params(labelsize=8)
    ax.axvline(2025.5, color="k", lw=0.5, ls=":")
axes.flat[0].legend(fontsize=8)
fig.suptitle("Thailand flood exposure by year (2019-2025) with linear projection to 2028\n"
             "(shaded band = ±1 SE of trend residuals; flood exposure is highly volatile — "
             "treat projections as trend indication only)", fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(os.path.join(FIG, "4_yearly_exposure_projection.png"), dpi=150)
plt.close(fig)
pd.DataFrame(proj_rows).to_csv(os.path.join(OUTT, "national_projection_2026_2028.csv"),
                               index=False, encoding="utf-8-sig")
nat.to_csv(os.path.join(OUTT, "national_yearly_exposure.csv"), encoding="utf-8-sig")

# ============================================================================
# 5) Heatmap: top-20 provinces x year (affected people)
# ============================================================================
hm = pv.pivot_table(index="province", columns="year", values="affected_people", aggfunc="sum")
hm = hm.loc[top20.index].fillna(0)
fig, ax = plt.subplots(figsize=(10, 8))
im = ax.imshow(hm.values + 1, cmap="YlOrRd", aspect="auto",
               norm=LogNorm(vmin=1, vmax=max(hm.values.max(), 10)))
ax.set_xticks(range(len(hm.columns)), hm.columns)
ax.set_yticks(range(len(hm.index)), hm.index, fontsize=9)
for i in range(hm.shape[0]):
    for j in range(hm.shape[1]):
        v = hm.values[i, j]
        ax.text(j, i, f"{v/1e3:.0f}K" if v >= 1e3 else f"{v:.0f}",
                ha="center", va="center", fontsize=7,
                color="white" if v > hm.values.max() / 8 else "black")
fig.colorbar(im, ax=ax, label="Affected people (log scale)")
ax.set_title("Flood-affected people by year — Top 20 exposed provinces")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "5_heatmap_top20_by_year.png"), dpi=150)
plt.close(fig)

# ============================================================================
# 6) Risk level overview: distribution + all provinces ranked
# ============================================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 12), width_ratios=[1, 2.2])
cnt = risk["risk_level"].value_counts().reindex(labels5)
ax1.bar(range(5), cnt.values, color=[LEVEL_COLORS[l] for l in labels5], edgecolor="grey")
ax1.set_xticks(range(5), [l.replace(" - ", "\n") for l in labels5], fontsize=9)
ax1.set_ylabel("Number of provinces")
ax1.set_title("Provinces per risk level (quintiles of composite score)")
for i, v in enumerate(cnt.values):
    ax1.text(i, v + 0.2, str(v), ha="center")

r = risk.iloc[::-1]
ax2.barh(r.index, r["exposure_score"],
         color=[LEVEL_COLORS[str(l)] for l in r["risk_level"]], edgecolor="grey", lw=0.3)
ax2.tick_params(axis="y", labelsize=6.5)
ax2.set_xlabel("Composite exposure score (0-100)")
ax2.set_title("All 77 provinces ranked — 5-level flood risk classification (2019-2025)")
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in LEVEL_COLORS.values()]
ax2.legend(handles, LEVEL_COLORS.keys(), title="Risk level", loc="lower right")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "6_risk_levels_all_provinces.png"), dpi=150)
plt.close(fig)

print("=== TOP 20 PROVINCES (composite) ===")
print(top20[["exposure_score", "risk_level", "years_affected", "affected_people",
             "housing_units", "agriculture_rai", "deaths"]].to_string())
print("\n=== RISK LEVEL COUNTS ===")
print(risk["risk_level"].value_counts().reindex(labels5).to_string())
print("\n=== TOP 10 DISTRICTS ===")
print(dist.head(10).to_string())
print("\n=== PROJECTION (affected_people) ===")
print(pd.DataFrame(proj_rows).query("dimension=='affected_people'").to_string(index=False))
print("\nDone. Figures ->", FIG)

"""
Outputs (in ./output and ./figures):
  1. Top-20 exposed areas (provinces by composite score + per-dimension; districts)
  2. National yearly exposure per dimension with linear projection to 2028
  3. 5-level risk categorization of all 77 provinces
  4. Heatmap of top-20 provinces x year
"""
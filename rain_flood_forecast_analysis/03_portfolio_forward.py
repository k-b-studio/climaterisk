# -*- coding: utf-8 -*-
"""
03_portfolio_forward.py
===================================================================
PURPOSE  (analysis requirement 4: "portfolio affected")
    Translate the 2026 forward-looking flood risk into the three lending
    portfolios that flood damage hits through different collateral channels:
        - Mortgage              (home = collateral; housing damage is direct)
        - Business loan / SME   (unlisted firms; premises, inventory, agri)
        - Automobile / HP       (vehicle = near-total loss when inundated)

METHOD
    Each portfolio gets its own forward score that blends:
      50%  flood-forecast share (the 2026 hazard, from the flood model)
      50%  portfolio-specific historical VULNERABILITY (the damage dimensions
           that map to THAT portfolio's collateral, 2019-2025)
    Rainfall is excluded from the score (geographically confounded - 02 §3);
    same 50/50 split as the base index, only the history component is
    re-weighted per portfolio. Output is a per-portfolio top-20 list, 5-level
    class, and a region exposure view.

INPUTS   (produced by 01 and 02)
    data/historical_province_year.csv        - portfolio-specific damage dims
    output/forward_risk_scores_2026.csv      - f_flood (already normalized)
===================================================================
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# ===================================================================
# SECTION 0 - Paths, style, load
# ===================================================================
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
FIG = os.path.join(BASE, "figures")
OUT = os.path.join(BASE, "output")

plt.rcParams["font.family"] = "Thonburi"
plt.rcParams["axes.unicode_minus"] = False

hist = pd.read_csv(os.path.join(DATA, "historical_province_year.csv"))
fwd = pd.read_csv(os.path.join(OUT, "forward_risk_scores_2026.csv"), index_col="province")
meta = pd.read_csv(os.path.join(DATA, "province_meta.csv")).set_index("province")

WEIGHTS = {"flood": 0.50, "hist": 0.50}     # same as the base index (rain excluded - see 02 §3)
LEVELS = ["1 - Very Low", "2 - Low", "3 - Moderate", "4 - High", "5 - Very High"]
LEVEL_COLORS = {LEVELS[0]: "#2c7bb6", LEVELS[1]: "#abd9e9", LEVELS[2]: "#ffffbf",
                LEVELS[3]: "#fdae61", LEVELS[4]: "#d7191c"}


def norm_log(s):
    """log1p then min-max to [0,1] (heavy-tailed damage counts)."""
    s = np.log1p(s.astype(float))
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng > 0 else s * 0.0


# ===================================================================
# SECTION 1 - PORTFOLIO DEFINITIONS
#   For each portfolio, the historical damage dimensions that map to its
#   collateral / borrower-cash-flow channel, with weights summing to 1.
#   This is the single place to change the portfolio logic.
# ===================================================================
PORTFOLIOS = {
    "mortgage":     {"housing_units": 0.50, "affected_households": 0.30, "affected_people": 0.20},
    "business_sme": {"business_sites": 0.40, "agriculture_rai": 0.30,
                     "affected_households": 0.20, "infrastructure_sites": 0.10},
    "automobile":   {"housing_units": 0.40, "evacuated_people": 0.30, "affected_people": 0.30},
}
PORT_LABELS = {"mortgage": "Mortgage (housing collateral)",
               "business_sme": "Business / SME (unlisted)",
               "automobile": "Automobile / HP"}

# ===================================================================
# SECTION 2 - Portfolio-specific historical vulnerability (cumulative 2019-2025)
# ===================================================================
cum = hist.groupby("province")[
    ["housing_units", "affected_households", "affected_people",
     "business_sites", "agriculture_rai", "infrastructure_sites", "evacuated_people"]
].sum(min_count=1).fillna(0)

vuln = pd.DataFrame(index=cum.index)
for pf, dims in PORTFOLIOS.items():
    vuln[pf] = sum(norm_log(cum[d]) * w for d, w in dims.items())   # weighted 0-1 composite

# ===================================================================
# SECTION 3 - Build the three forward-looking portfolio scores
#   forward = 0.45*flood-forecast + 0.40*portfolio vulnerability + 0.15*rain
# ===================================================================
base = fwd[["region_en", "f_flood", "flood_atrisk_share"]].copy()
port = base.copy()
for pf in PORTFOLIOS:
    raw = (WEIGHTS["flood"] * base["f_flood"]
           + WEIGHTS["hist"] * vuln[pf].reindex(base.index).fillna(0))
    port[f"{pf}_score"] = (100 * raw / raw.max()).round(2)
    # 5-level class on rank (tie-safe)
    port[f"{pf}_level"] = pd.qcut(port[f"{pf}_score"].rank(method="first"), 5, labels=LEVELS)

port = port.sort_values("mortgage_score", ascending=False)
port.to_csv(os.path.join(OUT, "portfolio_forward_scores_2026.csv"), encoding="utf-8-sig")

# Per-portfolio top-20 (long form for easy reading)
top20_long = []
for pf in PORTFOLIOS:
    t = port.sort_values(f"{pf}_score", ascending=False).head(20)
    for rank, (prov, row) in enumerate(t.iterrows(), 1):
        top20_long.append({"portfolio": pf, "rank": rank, "province": prov,
                           "region": row["region_en"], "score": row[f"{pf}_score"],
                           "level": row[f"{pf}_level"]})
pd.DataFrame(top20_long).to_csv(os.path.join(OUT, "top20_by_portfolio_2026.csv"),
                                index=False, encoding="utf-8-sig")

# ===================================================================
# SECTION 4 - Region exposure per portfolio (where each book is most exposed)
# ===================================================================
region_port = port.groupby("region_en")[[f"{pf}_score" for pf in PORTFOLIOS]].mean().round(2)
region_port.columns = list(PORTFOLIOS)
region_port = region_port.sort_values("mortgage", ascending=False)
region_port.to_csv(os.path.join(OUT, "portfolio_region_exposure_2026.csv"), encoding="utf-8-sig")

# ===================================================================
# SECTION 5 - FIGURES
# ===================================================================
# --- P1: three top-20 panels, colored by 5-level risk -----------------------
fig, axes = plt.subplots(1, 3, figsize=(22, 9))
for ax, pf in zip(axes, PORTFOLIOS):
    t = port.sort_values(f"{pf}_score", ascending=False).head(20).iloc[::-1]
    ax.barh(t.index, t[f"{pf}_score"],
            color=[LEVEL_COLORS[str(l)] for l in t[f"{pf}_level"]], edgecolor="grey", lw=0.4)
    for i, v in enumerate(t[f"{pf}_score"]):
        ax.text(v + 0.6, i, f"{v:.0f}", va="center", fontsize=8)
    ax.set_xlim(0, 112); ax.tick_params(labelsize=8)
    ax.set_title(PORT_LABELS[pf], fontsize=11)
    ax.set_xlabel("2026 forward portfolio risk score")
fig.suptitle("Top 20 จังหวัด by 2026 forward-looking flood risk — per credit portfolio\n"
             "(50% flood-forecast + 50% portfolio-specific damage history)",
             fontsize=13)
axes[0].legend(handles=[Patch(color=c, label=l) for l, c in LEVEL_COLORS.items()],
               title="Risk level", loc="lower right", fontsize=8)
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(os.path.join(FIG, "P1_top20_by_portfolio_2026.png"), dpi=150)
plt.close(fig)

# --- P2: region x portfolio exposure heatmap --------------------------------
fig, ax = plt.subplots(figsize=(7.5, 5))
im = ax.imshow(region_port.values, cmap="YlOrRd", aspect="auto")
ax.set_xticks(range(len(PORTFOLIOS)), [PORT_LABELS[p] for p in PORTFOLIOS],
              rotation=20, ha="right", fontsize=9)
ax.set_yticks(range(len(region_port)), region_port.index, fontsize=9)
for i in range(region_port.shape[0]):
    for j in range(region_port.shape[1]):
        v = region_port.values[i, j]
        ax.text(j, i, f"{v:.0f}", ha="center", va="center",
                color="white" if v > region_port.values.max() * 0.6 else "black", fontsize=9)
fig.colorbar(im, ax=ax, label="mean forward portfolio score")
ax.set_title("Where each portfolio is most exposed (2026, by region)")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "P2_region_portfolio_heatmap.png"), dpi=150)
plt.close(fig)

# ===================================================================
# SECTION 6 - Console summary
# ===================================================================
print("PORTFOLIO FORWARD SCORES (2026) — top 10 per portfolio:")
for pf in PORTFOLIOS:
    t = port.sort_values(f"{pf}_score", ascending=False).head(10)
    print(f"\n{PORT_LABELS[pf]}:")
    print(t[[f"{pf}_score", f"{pf}_level", "region_en"]].to_string())
print("\nREGION x PORTFOLIO mean exposure:")
print(region_port.to_string())
print("\nDone. Figures -> P1,P2 | Tables -> output/portfolio_*.csv, top20_by_portfolio_2026.csv")

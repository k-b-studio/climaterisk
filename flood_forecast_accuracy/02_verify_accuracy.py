"""
02_verify_accuracy.py
---------------------
Score HII 6-month flood forecasts using categorical forecast-verification
metrics. For each target month T, the lead-0 assessment (made in month T,
the "reporting month") is treated as observed truth; the forecasts issued
1..5 months earlier (lead 1..5) are scored against it.

Scoring window (target months) : 2025-06 .. 2026-06  ("since month 6 of last
year to present").

Event of interest : a tambon is flagged FLOOD if its class is
'flood risk' or 'flashflood' (vs 'norisk'). Floods are rare (~1-8% of
tambons), so we report skill scores designed for rare events rather than raw
accuracy, which is dominated by correct 'norisk' calls.

Contingency table (per lead, pooled over tambon x target month):
    H  hits           forecast flood, observed flood
    F  false alarms   forecast flood, observed norisk
    M  misses         forecast norisk, observed flood
    CN correct neg.   forecast norisk, observed norisk

    POD (recall/hit rate) = H / (H + M)          [1 best, 0 worst]
    FAR (false-alarm ratio)= F / (H + F)          [0 best, 1 worst]
    SR  (success/precision)= H / (H + F) = 1-FAR
    CSI (critical success) = H / (H + M + F)      [1 best] -- headline skill
    BIAS                   = (H + F) / (H + M)     [1 unbiased; >1 over-warn]
    HSS (Heidke skill)     vs random              [1 perfect; 0 no skill]
    ACC (accuracy)         = (H + CN) / N
    f3  exact 3-class accuracy (norisk/flood risk/flashflood)

Outputs: output/S1..S6 csv tables, figures/F1..F6 png.
"""
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "output")
FIG = os.path.join(HERE, "figures")
for d in (OUT, FIG):
    os.makedirs(d, exist_ok=True)

WIN_START, WIN_END = 2025 * 12 + 5, 2026 * 12 + 5  # 2025-06 .. 2026-06 inclusive
LEADS = [1, 2, 3, 4, 5]
FLOOD = {"flood risk", "flashflood"}

plt.rcParams.update({
    "figure.dpi": 120,
    "savefig.dpi": 150,
    "font.size": 10,
    "axes.titleweight": "bold",
    "axes.grid": True,
    "grid.alpha": 0.25,
})
ACCENT = "#1f6f8b"


# ----------------------------------------------------------------------------- helpers
def contingency(obs_flood, fc_flood):
    """obs_flood, fc_flood: boolean arrays. Returns H, F, M, CN."""
    H = int(np.sum(fc_flood & obs_flood))
    F = int(np.sum(fc_flood & ~obs_flood))
    M = int(np.sum(~fc_flood & obs_flood))
    CN = int(np.sum(~fc_flood & ~obs_flood))
    return H, F, M, CN


def skill_scores(H, F, M, CN):
    N = H + F + M + CN
    pod = H / (H + M) if (H + M) else np.nan
    far = F / (H + F) if (H + F) else np.nan
    sr = 1 - far if not np.isnan(far) else np.nan
    csi = H / (H + M + F) if (H + M + F) else np.nan
    bias = (H + F) / (H + M) if (H + M) else np.nan
    acc = (H + CN) / N if N else np.nan
    denom = (H + M) * (M + CN) + (H + F) * (F + CN)
    hss = (2 * (H * CN - M * F) / denom) if denom else np.nan
    return dict(N=N, H=H, F=F, M=M, CN=CN, POD=pod, FAR=far, SR=sr,
               CSI=csi, BIAS=bias, ACC=acc, HSS=hss)


# ----------------------------------------------------------------------------- load
vt = pd.read_csv(os.path.join(DATA, "verification_table.csv"))
vt = vt[(vt["target_idx"] >= WIN_START) & (vt["target_idx"] <= WIN_END)].copy()
vt = vt.dropna(subset=["lead_0"])  # require a reporting-month truth
months = sorted(vt["target_idx"].unique())
print(f"Scoring window: {vt['target_label'].min()} .. {vt['target_label'].max()} "
      f"({len(months)} target months, {len(vt):,} tambon-months)")

obs_flood = vt["lead_0"].isin(FLOOD).values


# ============================================================ S1: metrics by lead (pooled)
rows = []
for L in LEADS:
    col = f"lead_{L}"
    valid = vt[col].notna().values
    fc_flood = vt[col].isin(FLOOD).values
    H, F, M, CN = contingency(obs_flood[valid], fc_flood[valid])
    sc = skill_scores(H, F, M, CN)
    # exact 3-class accuracy
    f3 = float(np.mean(vt.loc[valid, col].values == vt.loc[valid, "lead_0"].values))
    sc.update(lead=L, lead_months=L, f3_accuracy=f3)
    rows.append(sc)
s1 = pd.DataFrame(rows)[
    ["lead", "N", "H", "F", "M", "CN", "POD", "FAR", "SR", "CSI", "BIAS",
     "ACC", "HSS", "f3_accuracy"]
]
s1.to_csv(os.path.join(OUT, "S1_metrics_by_lead.csv"), index=False)
print("\n=== S1: skill by lead time (pooled over window) ===")
print(s1.round(3).to_string(index=False))

# baseline: observed event rate
event_rate = obs_flood.mean()
print(f"\nObserved flood base rate (lead-0): {event_rate:.3%} of tambon-months")


# ============================================================ S2: metrics by target month x lead
rows = []
for t in months:
    sub = vt[vt["target_idx"] == t]
    o = sub["lead_0"].isin(FLOOD).values
    for L in LEADS:
        col = f"lead_{L}"
        valid = sub[col].notna().values
        if valid.sum() == 0:
            continue
        fc = sub[col].isin(FLOOD).values
        H, F, M, CN = contingency(o[valid], fc[valid])
        sc = skill_scores(H, F, M, CN)
        sc.update(target_idx=t, target_label=sub["target_label"].iloc[0], lead=L,
                  obs_flood_n=int(o.sum()))
        rows.append(sc)
s2 = pd.DataFrame(rows)
s2.to_csv(os.path.join(OUT, "S2_metrics_by_target_lead.csv"), index=False)


# ============================================================ S3: 3-class confusion per lead
classes = ["norisk", "flood risk", "flashflood"]
conf_rows = []
for L in LEADS:
    col = f"lead_{L}"
    valid = vt[col].notna()
    ct = pd.crosstab(vt.loc[valid, "lead_0"], vt.loc[valid, col]).reindex(
        index=classes, columns=classes).fillna(0).astype(int)
    for obs in classes:
        for fc in classes:
            conf_rows.append(dict(lead=L, observed=obs, forecast=fc, n=ct.loc[obs, fc]))
s3 = pd.DataFrame(conf_rows)
s3.to_csv(os.path.join(OUT, "S3_confusion_by_lead.csv"), index=False)


# ============================================================ S4: region x lead CSI/POD
reg_rows = []
for reg, g in vt.groupby("REGION_E"):
    o = g["lead_0"].isin(FLOOD).values
    for L in LEADS:
        col = f"lead_{L}"
        valid = g[col].notna().values
        fc = g[col].isin(FLOOD).values
        H, F, M, CN = contingency(o[valid], fc[valid])
        sc = skill_scores(H, F, M, CN)
        reg_rows.append(dict(region=reg, lead=L, CSI=sc["CSI"], POD=sc["POD"],
                             FAR=sc["FAR"], obs_flood_n=int(o.sum())))
s4 = pd.DataFrame(reg_rows)
s4.to_csv(os.path.join(OUT, "S4_region_by_lead.csv"), index=False)


# ============================================================ S5: severity-specific detection
# For each observed severity class, how often did the lead-L forecast capture it
# (recall to exact class, and recall to "any flood")?
sev_rows = []
for sev in ["flood risk", "flashflood"]:
    obs_mask = (vt["lead_0"] == sev).values
    for L in LEADS:
        col = f"lead_{L}"
        valid = vt[col].notna().values
        m = obs_mask & valid
        n = int(m.sum())
        exact = float(np.mean(vt.loc[m, col].values == sev)) if n else np.nan
        anyflood = float(np.mean(vt.loc[m, col].isin(FLOOD).values)) if n else np.nan
        sev_rows.append(dict(observed_severity=sev, lead=L, n_events=n,
                             recall_exact=exact, recall_anyflood=anyflood))
s5 = pd.DataFrame(sev_rows)
s5.to_csv(os.path.join(OUT, "S5_severity_detection.csv"), index=False)


# ============================================================ S6: warned-tambon counts (reported vs forecast)
cnt_rows = []
for t in months:
    sub = vt[vt["target_idx"] == t]
    row = dict(target_idx=t, target_label=sub["target_label"].iloc[0],
               reported=int(sub["lead_0"].isin(FLOOD).sum()))
    for L in LEADS:
        row[f"forecast_lead{L}"] = int(sub[f"lead_{L}"].isin(FLOOD).sum())
    cnt_rows.append(row)
s6 = pd.DataFrame(cnt_rows)
s6.to_csv(os.path.join(OUT, "S6_warned_counts.csv"), index=False)


# =================================================================== FIGURES
def lbls(ms):
    return [pd.read_csv  # placeholder no-op to keep linter quiet
            ] and [f"{m // 12}-{m % 12 + 1:02d}" for m in ms]


# ---- F1: headline skill vs lead time --------------------------------------
fig, ax = plt.subplots(1, 2, figsize=(12, 5))
ax[0].plot(s1["lead"], s1["POD"], "o-", color="#2a9d8f", label="POD (detection)", lw=2)
ax[0].plot(s1["lead"], s1["SR"], "s-", color="#e76f51", label="Success ratio (1-FAR)", lw=2)
ax[0].plot(s1["lead"], s1["CSI"], "D-", color=ACCENT, label="CSI (overall skill)", lw=2.5)
ax[0].plot(s1["lead"], s1["HSS"], "^-", color="#8338ec", label="HSS (Heidke skill)", lw=2)
ax[0].set_xlabel("Forecast lead time (months ahead)")
ax[0].set_ylabel("Score")
ax[0].set_title("Flood-warning skill vs lead time")
ax[0].set_xticks(LEADS)
ax[0].set_ylim(0, 1)
ax[0].legend(fontsize=8, loc="upper right")

ax[1].plot(s1["lead"], s1["BIAS"], "o-", color="#d62828", lw=2.5, label="Frequency bias")
ax[1].axhline(1.0, color="grey", ls="--", lw=1, label="unbiased (1.0)")
ax[1].set_xlabel("Forecast lead time (months ahead)")
ax[1].set_ylabel("Bias = forecast / observed flood frequency")
ax[1].set_title("Over- / under-warning by lead time")
ax[1].set_xticks(LEADS)
ax[1].legend(fontsize=8)
fig.suptitle("HII 6-month flood forecast — verification vs reporting-month assessment "
             f"(targets {vt['target_label'].min()}…{vt['target_label'].max()})",
             fontsize=11, y=1.02)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "F1_skill_vs_leadtime.png"), bbox_inches="tight")
plt.close(fig)


# ---- F2: CSI heatmap target month x lead ----------------------------------
piv = s2.pivot(index="target_label", columns="lead", values="CSI")
piv = piv.reindex([f"{m // 12}-{m % 12 + 1:02d}" for m in months])
fig, ax = plt.subplots(figsize=(7, 8))
cmap = LinearSegmentedColormap.from_list("csi", ["#f7f7f7", "#a8dadc", ACCENT, "#14213d"])
im = ax.imshow(piv.values, aspect="auto", cmap=cmap, vmin=0, vmax=max(0.6, np.nanmax(piv.values)))
ax.set_xticks(range(len(LEADS)))
ax.set_xticklabels([f"+{L}m" for L in LEADS])
ax.set_yticks(range(len(piv)))
ax.set_yticklabels(piv.index)
ax.set_xlabel("Lead time")
ax.set_title("Forecast skill (CSI) by target month and lead")
for i in range(piv.shape[0]):
    for j in range(piv.shape[1]):
        v = piv.values[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if v > 0.35 else "#222", fontsize=8)
fig.colorbar(im, ax=ax, label="CSI", fraction=0.046, pad=0.04)
ax.grid(False)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "F2_csi_heatmap.png"), bbox_inches="tight")
plt.close(fig)


# ---- F3: 3-class confusion matrices (row-normalized) per lead -------------
fig, axes = plt.subplots(1, len(LEADS), figsize=(4 * len(LEADS) * 0.8, 4))
short = ["norisk", "flood", "flash"]
for k, L in enumerate(LEADS):
    sub = s3[s3["lead"] == L]
    mat = sub.pivot(index="observed", columns="forecast", values="n").reindex(
        index=classes, columns=classes).values.astype(float)
    norm = mat / mat.sum(axis=1, keepdims=True)
    ax = axes[k]
    im = ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_title(f"lead +{L}m")
    ax.set_xticks(range(3)); ax.set_xticklabels(short, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(3)); ax.set_yticklabels(short if k == 0 else [], fontsize=8)
    if k == 0:
        ax.set_ylabel("Observed (reported)")
    ax.set_xlabel("Forecast")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{norm[i, j]:.2f}", ha="center", va="center",
                    color="white" if norm[i, j] > 0.5 else "#222", fontsize=8)
    ax.grid(False)
fig.suptitle("Row-normalized confusion matrices — what earlier forecasts said, "
             "given what was reported", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "F3_confusion_by_lead.png"), bbox_inches="tight")
plt.close(fig)


# ---- F4: warned-tambon count time series ----------------------------------
fig, ax = plt.subplots(figsize=(12, 5.5))
x = range(len(s6))
ax.bar(x, s6["reported"], color="#14213d", label="Reported (lead-0)", zorder=3, width=0.6)
palette = ["#2a9d8f", "#8ab17d", "#e9c46a", "#f4a261", "#e76f51"]
for L, c in zip(LEADS, palette):
    ax.plot(x, s6[f"forecast_lead{L}"], "o-", color=c, lw=1.8, ms=4,
            label=f"Forecast {L}m earlier")
ax.set_xticks(list(x))
ax.set_xticklabels(s6["target_label"], rotation=45, ha="right")
ax.set_ylabel("# tambons flagged flood / flashflood")
ax.set_title("Reported flood extent vs what was forecast 1–5 months earlier")
ax.legend(fontsize=8, ncol=3)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "F4_warned_counts_timeseries.png"), bbox_inches="tight")
plt.close(fig)


# ---- F5: region x lead CSI heatmap ----------------------------------------
rp = s4.pivot(index="region", columns="lead", values="CSI")
order = rp.mean(axis=1).sort_values(ascending=False).index
rp = rp.reindex(order)
fig, ax = plt.subplots(figsize=(7, 4.5))
im = ax.imshow(rp.values, aspect="auto", cmap=cmap, vmin=0, vmax=max(0.6, np.nanmax(rp.values)))
ax.set_xticks(range(len(LEADS))); ax.set_xticklabels([f"+{L}m" for L in LEADS])
ax.set_yticks(range(len(rp))); ax.set_yticklabels(rp.index)
ax.set_title("Forecast skill (CSI) by region and lead")
ax.set_xlabel("Lead time")
for i in range(rp.shape[0]):
    for j in range(rp.shape[1]):
        v = rp.values[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if v > 0.35 else "#222", fontsize=8)
fig.colorbar(im, ax=ax, label="CSI", fraction=0.046, pad=0.04)
ax.grid(False)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "F5_region_csi_heatmap.png"), bbox_inches="tight")
plt.close(fig)


# ---- F6: severity detection (recall) vs lead ------------------------------
fig, ax = plt.subplots(figsize=(8, 5))
styles = {"flood risk": ("#457b9d", "o"), "flashflood": ("#e63946", "s")}
for sev, (c, mk) in styles.items():
    d = s5[s5["observed_severity"] == sev]
    ax.plot(d["lead"], d["recall_anyflood"], mk + "-", color=c, lw=2.2,
            label=f"{sev}: detected as any-flood")
    ax.plot(d["lead"], d["recall_exact"], mk + "--", color=c, lw=1.5, alpha=0.7,
            label=f"{sev}: detected as exact class")
ax.set_xlabel("Forecast lead time (months ahead)")
ax.set_ylabel("Detection rate (recall)")
ax.set_title("How early were reported floods captured, by severity?")
ax.set_xticks(LEADS); ax.set_ylim(0, 1)
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "F6_severity_detection.png"), bbox_inches="tight")
plt.close(fig)

print("\nFigures written to figures/  (F1..F6)")
print("Tables written to output/  (S1..S6)")
print("\n=== S5: severity detection (recall) ===")
print(s5.round(3).to_string(index=False))

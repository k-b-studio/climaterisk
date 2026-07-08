from __future__ import annotations
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
import config as C

MONTH_NAME = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
              7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
AGREE_ORDER = ["NEITHER", "HISTORY_ONLY", "FORECAST_ONLY", "BOTH"]
AGREE_COLOR = {"NEITHER": "#eeeeee", "HISTORY_ONLY": "#fdae61",
               "FORECAST_ONLY": "#5e3c99", "BOTH": "#1a9641"}


def load_hist() -> pd.DataFrame:
    df = pd.read_csv(C.HIST_CSV)
    df["GEOCODE"] = df["GEOCODE"].astype(str).str.strip()
    df["HLEVEL"] = df["RISK"].map(C.HIST_RISK_LEVEL).fillna(0).astype(int)
    df = df.rename(columns={"COUNT 17 YEAR": "HCOUNT"})
    return df[["Month", "GEOCODE", "HCOUNT", "HLEVEL"]]


def hist_window(hist: pd.DataFrame, months: list[int]) -> pd.DataFrame:
    """Aggregate historical risk over a set of calendar months, per Tambon."""
    sub = hist[hist["Month"].isin(months)]
    g = sub.groupby("GEOCODE").agg(
        HCOUNT_MAX=("HCOUNT", "max"),
        HLEVEL_MAX=("HLEVEL", "max"),
        HMONTHS=("Month", "nunique"),       # how many of the window months flood
    ).reset_index()
    return g


def build_agreement(by_issue, hist, pers):
    universe = sorted(by_issue["GEOCODE"].unique())   # all forecast Tambons
    recs = []
    for m in range(1, 13):
        if m not in set(by_issue["ISSUE_MONTH"]):
            continue
        months = [m]   # SAME month vs SAME month: report-month M vs history month M
        gi = by_issue[by_issue["ISSUE_MONTH"] == m]
        # forecast footprint across years
        fc = gi.groupby("GEOCODE").agg(
            FC_FLASH=("IS_FLASH", "any"),
            FC_FLOOD=("IS_FLOOD", "any"),
            FC_ANY=("AT_RISK", "any"),
        )
        hw = hist_window(hist, months).set_index("GEOCODE")
        pv = (pers[pers.ISSUE_MONTH == m]
              .set_index("GEOCODE")[["FLASH_NYEARS", "FLOOD_NYEARS", "N_YEARS"]])
        df = pd.DataFrame(index=universe)
        df["ISSUE_MONTH"] = m
        df = df.join(fc).join(hw).join(pv)
        for c in ["FC_FLASH", "FC_FLOOD", "FC_ANY"]:
            df[c] = df[c].fillna(False)
        for c in ["HCOUNT_MAX", "HLEVEL_MAX", "HMONTHS",
                  "FLASH_NYEARS", "FLOOD_NYEARS"]:
            df[c] = df[c].fillna(0).astype(int)
        df["N_YEARS"] = df["N_YEARS"].fillna(df["N_YEARS"].dropna().max()).astype(int)
        df["FC"] = df["FC_ANY"]
        df["HIST"] = df["HLEVEL_MAX"] > 0
        df["PERS"] = df[["FLASH_NYEARS", "FLOOD_NYEARS"]].max(axis=1)  # max persistence
        df["AGREE"] = np.select(
            [df.FC & df.HIST, df.FC & ~df.HIST, ~df.FC & df.HIST],
            ["BOTH", "FORECAST_ONLY", "HISTORY_ONLY"], default="NEITHER")
        recs.append(df.reset_index().rename(columns={"index": "GEOCODE"}))
    return pd.concat(recs, ignore_index=True)


def validation_summary(agree: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for m, d in agree.groupby("ISSUE_MONTH"):
        nfc = int(d.FC.sum()); nhist = int(d.HIST.sum())
        both = int((d.AGREE == "BOTH").sum())
        fo = int((d.AGREE == "FORECAST_ONLY").sum())
        ho = int((d.AGREE == "HISTORY_ONLY").sum())

        prec = both / nfc if nfc else np.nan
        rec = both / nhist if nhist else np.nan

        hi = d[d.HLEVEL_MAX == 3]
        rec_hi = (hi.FC.sum() / len(hi)) if len(hi) else np.nan
        rows.append({
            "ISSUE_MONTH": m, "MONTH": MONTH_NAME[m],
            "HIST_MONTH": MONTH_NAME[m],  
            "N_FORECAST": nfc, "N_HIST": nhist, "BOTH": both,
            "FORECAST_ONLY": fo, "HISTORY_ONLY": ho,
            "PRECISION_vs_hist": round(prec, 3),
            "RECALL_vs_hist": round(rec, 3),
            "RECALL_hist_HIGH": round(rec_hi, 3) if rec_hi == rec_hi else np.nan,
        })
    return pd.DataFrame(rows)


def persistence_vs_history(agree: pd.DataFrame) -> pd.DataFrame:
    
    d = agree[agree.FC].copy()
    d["PERS_LABEL"] = d["PERS"].astype(int).astype(str) + " yr"
    ct = pd.crosstab(d["PERS"], d["HLEVEL_MAX"].map(C.HIST_LEVEL_EN),
                     normalize="index").round(3)
    ct.columns.name = "historical_risk"
    ct.index.name = "forecast_persistence_years"

    mean_cnt = d.groupby("PERS")["HCOUNT_MAX"].mean().round(2)
    ct["mean_hist_count_17yr"] = mean_cnt
    ct["n_tambon_months"] = d.groupby("PERS").size()
    return ct.reset_index().rename(columns={"forecast_persistence_years": "PERS"})


# ---------------------------------------------------------------- maps
def plot_agreement(gdf, agree, m, ax=None, standalone=True):
    d = agree[agree.ISSUE_MONTH == m][["GEOCODE", "AGREE"]]
    g = gdf.merge(d, on="GEOCODE", how="left")
    g["AGREE"] = g["AGREE"].fillna("NEITHER")
    g["ACODE"] = g["AGREE"].map({a: i for i, a in enumerate(AGREE_ORDER)})
    cmap = ListedColormap([AGREE_COLOR[a] for a in AGREE_ORDER])
    norm = BoundaryNorm(np.arange(-0.5, 4.5, 1), cmap.N)
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 9))
    g.plot(column="ACODE", cmap=cmap, norm=norm, ax=ax, linewidth=0)
    g.boundary.plot(ax=ax, linewidth=0.05, color="white")
    ax.set_axis_off()
    vc = g["AGREE"].value_counts()
    ax.set_title(f"{MONTH_NAME[m]} report vs {MONTH_NAME[m]} history\n"
                 f"both={vc.get('BOTH',0)}  fc-only={vc.get('FORECAST_ONLY',0)}  "
                 f"hist-only={vc.get('HISTORY_ONLY',0)}", fontsize=9)
    if standalone:
        handles = [Patch(facecolor=AGREE_COLOR[a], edgecolor="grey", label=a)
                   for a in reversed(AGREE_ORDER)]
        ax.legend(handles=handles, loc="lower left", fontsize=8, frameon=True)
        fig = ax.figure
        out = C.FIG / "vs_retro" / f"agreement_month{m:02d}.png"
        fig.tight_layout(); fig.savefig(out, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return out


def contact_sheet(gdf, agree):
    months = sorted(agree.ISSUE_MONTH.unique())
    fig, axes = plt.subplots(3, 4, figsize=(20, 18))
    for ax, m in zip(axes.ravel(), months):
        plot_agreement(gdf, agree, m, ax=ax, standalone=False)
    handles = [Patch(facecolor=AGREE_COLOR[a], edgecolor="grey", label=a)
               for a in reversed(AGREE_ORDER)]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=12)
    fig.suptitle("Report-month footprint vs SAME-month 17-yr flood climatology",
                 fontsize=18, y=0.995)
    out = C.FIG / "vs_retro" / "_contact_agreement.png"
    fig.savefig(out, dpi=110, bbox_inches="tight"); plt.close(fig)
    return out


def plot_pers_vs_hist(pvh):
    levels = [c for c in ["none", "low", "medium", "high"] if c in pvh.columns]
    fig, ax = plt.subplots(figsize=(8, 5))
    bottom = np.zeros(len(pvh))
    colors = {"none": "#dddddd", "low": "#fee08b", "medium": "#fc8d59", "high": "#d73027"}
    for lv in levels:
        ax.bar(pvh["PERS"].astype(int).astype(str), pvh[lv], bottom=bottom,
               label=lv, color=colors[lv])
        bottom += pvh[lv].values
   
    ax.set_xlabel("Task-1 forecast persistence (years the report flagged the Tambon)")
    ax.set_ylabel("share of forecast-flagged Tambon-months")
    ax.set_title("TASK 2 - Do persistently-forecast areas match historical flood risk?")
    ax.legend(title="17-yr historical risk", loc="upper left", bbox_to_anchor=(1, 1))
    for i, (_, r) in enumerate(pvh.iterrows()):
        ax.text(i, 1.02, f"n={int(r['n_tambon_months'])}\nμcnt={r['mean_hist_count_17yr']}",
                ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    out = C.FIG / "vs_retro" / "persistence_vs_history.png"
    fig.savefig(out, dpi=130, bbox_inches="tight"); plt.close(fig)
    return out


def load_tambon_gdf():
    gdf = gpd.read_file(C.GEOJSON)
    gdf["GEOCODE"] = gdf["ADM3_PCODE"].map(C.geocode_from_pcode)
    gdf["geometry"] = gdf.geometry.simplify(0.004, preserve_topology=True)
    return gdf.dissolve(by="GEOCODE", as_index=False)[["GEOCODE", "geometry"]]


def main():
    by_issue = pd.read_pickle(C.OUT / "forecast_by_issue.pkl")
    by_issue = by_issue[by_issue["ISSUE_YEAR"].isin(C.ANALYSIS_YEARS)]
    print(f"analysis years = {C.ANALYSIS_YEARS}")
    pers = pd.read_csv(C.OUT / "_persistence.csv", dtype={"GEOCODE": str})
    hist = load_hist()

    print("1) building agreement table ...")
    agree = build_agreement(by_issue, hist, pers)
    agree.to_csv(C.OUT / "_agreement_byreport.csv", index=False)

    print("2) validation summary ...")
    summ = validation_summary(agree)
    summ.to_csv(C.OUT / "_validation_summary.csv", index=False)
    print(summ.to_string(index=False))

    print("\n3) persistence vs history ...")
    pvh = persistence_vs_history(agree)
    pvh.to_csv(C.OUT / "_persistence_vs_history.csv", index=False)
    print(pvh.to_string(index=False))

    print("\n4) rendering maps ...")
    gdf = load_tambon_gdf()
    for m in sorted(agree.ISSUE_MONTH.unique()):
        plot_agreement(gdf, agree, m)
    print("   ", contact_sheet(gdf, agree).name)
    print("   ", plot_pers_vs_hist(pvh).name)


    tot_both = int((agree.AGREE == "BOTH").sum())
    tot_fc = int(agree.FC.sum())
    tot_hist = int(agree.HIST.sum())
    print("\n========== TASK 2 HEADLINE ==========")
    print(f"Forecast-flagged Tambon-months ...... {tot_fc:,}")
    print(f"  of which historically flood ....... {tot_both:,} ({tot_both/tot_fc:.0%})  <- precision")
    print(f"Historically-flooding Tambon-months . {tot_hist:,}")
    print(f"  of which forecast flagged ......... {tot_both:,} ({tot_both/tot_hist:.0%})  <- recall")


if __name__ == "__main__":
    main()

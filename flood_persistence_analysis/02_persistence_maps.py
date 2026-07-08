from __future__ import annotations
import json
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

NONE_GREY = "#f0f0f0"   

FLASH_RAMP = {1: ["#cb181d"],
              2: ["#fcae91", "#cb181d"],
              3: ["#fcae91", "#fb6a4a", "#cb181d"]}
FLOOD_RAMP = {1: ["#2171b5"],
              2: ["#bdd7e7", "#2171b5"],
              3: ["#bdd7e7", "#6baed6", "#2171b5"]}


def shade_ramp(kind: str, n_years: int) -> list[str]:
    """[grey, light .. dark] with n_years data colours; ALWAYS = darkest."""
    ramp = FLASH_RAMP if kind == "FLASH" else FLOOD_RAMP
    return [NONE_GREY] + ramp[n_years]


def load_tambon_gdf() -> gpd.GeoDataFrame:
    print("  reading Tambon polygons ...")
    gdf = gpd.read_file(C.GEOJSON)
    gdf["GEOCODE"] = gdf["ADM3_PCODE"].map(C.geocode_from_pcode)

    gdf["geometry"] = gdf.geometry.simplify(0.004, preserve_topology=True)
    gdf = gdf.dissolve(by="GEOCODE", as_index=False) 
    return gdf[["GEOCODE", "ADM1_EN", "geometry"]]


def build_persistence(by_issue: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for m, grp in by_issue.groupby("ISSUE_MONTH"):
        years = sorted(grp["ISSUE_YEAR"].unique())
        n_years = len(years)
        flash = (grp[grp["IS_FLASH"]].groupby("GEOCODE")["ISSUE_YEAR"]
                 .apply(lambda s: sorted(s.unique())))
        flood = (grp[grp["IS_FLOOD"]].groupby("GEOCODE")["ISSUE_YEAR"]
                 .apply(lambda s: sorted(s.unique())))
        codes = set(flash.index) | set(flood.index)
        for gc in codes:
            fy = flash.get(gc, [])
            dy = flood.get(gc, [])
            rows.append({
                "ISSUE_MONTH": m, "N_YEARS": n_years, "GEOCODE": gc,
                "FLASH_NYEARS": len(fy), "FLOOD_NYEARS": len(dy),
                "FLASH_YEARS": ",".join(map(str, fy)),
                "FLOOD_YEARS": ",".join(map(str, dy)),
            })
    return pd.DataFrame(rows)


def _persistence_label(kind: str, n_years: int) -> list[str]:
    lab = ["not flagged"]
    for k in range(1, n_years + 1):
        if k == 1:
            lab.append(f"1 yr  (new)")
        elif k == n_years:
            lab.append(f"{k} yrs (always)")
        else:
            lab.append(f"{k} yrs")
    return lab


def plot_month(gdf, pers, m, kind, ax=None, standalone=True):
    col = "FLASH_NYEARS" if kind == "FLASH" else "FLOOD_NYEARS"
    title_kind = "Flash flood" if kind == "FLASH" else "Flood / inundation"

    sub = pers[pers["ISSUE_MONTH"] == m]
    n_years = int(sub["N_YEARS"].iloc[0]) if len(sub) else 0
    g = gdf.merge(sub[["GEOCODE", col]], on="GEOCODE", how="left")
    g[col] = g[col].fillna(0).astype(int)

    shades = shade_ramp(kind, n_years)
    cmap = ListedColormap(shades)
    norm = BoundaryNorm(np.arange(-0.5, n_years + 1.5, 1), cmap.N)

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 9))
    g.plot(column=col, cmap=cmap, norm=norm, ax=ax, linewidth=0)
    g.boundary.plot(ax=ax, linewidth=0.05, color="white")
    ax.set_axis_off()

    years_txt = ",".join(map(str, sorted(
        pers[pers.ISSUE_MONTH == m]
        .assign(y=0).index.map(lambda _: 0)))) if False else ""
    n_flagged = int((g[col] > 0).sum())
    n_always = int((g[col] == n_years).sum())
    ax.set_title(f"{MONTH_NAME[m]} report - {title_kind}\n"
                 f"{n_years} yrs compared | {n_flagged} Tambons flagged | "
                 f"{n_always} always", fontsize=10)

    if standalone:
        labels = _persistence_label(kind, n_years)
        handles = [Patch(facecolor=shades[i], edgecolor="grey",
                         label=labels[i]) for i in range(1, n_years + 1)]
        ax.legend(handles=handles, loc="lower left", fontsize=8,
                  title="appears in", frameon=True)
        fig = ax.figure
        fname = C.FIG / "forecast_merge" / f"{kind.lower()}_month{m:02d}.png"
        fig.tight_layout()
        fig.savefig(fname, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return fname


def contact_sheet(gdf, pers, kind):
    months = sorted(pers["ISSUE_MONTH"].unique())
    fig, axes = plt.subplots(3, 4, figsize=(20, 18))
    for ax, m in zip(axes.ravel(), months):
        plot_month(gdf, pers, m, kind, ax=ax, standalone=False)
    n_years = int(pers["N_YEARS"].max())
    shades = shade_ramp(kind, n_years)
    labels = _persistence_label(kind, n_years)
    handles = [Patch(facecolor=shades[i], edgecolor="grey", label=labels[i])
               for i in range(1, n_years + 1)]
    fig.legend(handles=handles, loc="lower center", ncol=n_years, fontsize=12,
               title="appears in N of the compared years")
    kind_t = "Flash flood (red)" if kind == "FLASH" else "Flood / inundation (blue)"
    fig.suptitle(f"Same-month-report persistence across years - {kind_t}",
                 fontsize=18, y=0.995)
    out = C.FIG / "forecast_merge" / f"_contact_{kind.lower()}.png"
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out


def main():
    by_issue = pd.read_pickle(C.OUT / "forecast_by_issue.pkl")
    by_issue = by_issue[by_issue["ISSUE_YEAR"].isin(C.ANALYSIS_YEARS)]
    print(f"   analysis years = {C.ANALYSIS_YEARS}")
    print("1) building persistence table ...")
    pers = build_persistence(by_issue)
    pers.to_csv(C.OUT / "_persistence.csv", index=False)
    print(f"   wrote _persistence.csv  ({len(pers):,} rows)")

    gdf = load_tambon_gdf()

    print("2) rendering per-month maps ...")
    for m in sorted(pers["ISSUE_MONTH"].unique()):
        for kind in ("FLASH", "FLOOD"):
            f = plot_month(gdf, pers, m, kind)
            print(f"   {f.name}")

    print("3) rendering contact sheets ...")
    for kind in ("FLASH", "FLOOD"):
        print("  ", contact_sheet(gdf, pers, kind).name)

    print("\n========== TASK 1 STABILITY SUMMARY ==========")
    for m, sub in pers.groupby("ISSUE_MONTH"):
        ny = int(sub["N_YEARS"].iloc[0])
        for kind, col in (("flash", "FLASH_NYEARS"), ("flood", "FLOOD_NYEARS")):
            s = sub[sub[col] > 0]
            if len(s) == 0:
                continue
            always = (s[col] == ny).sum()
            new = (s[col] == 1).sum()
            print(f"  month {m:>2} {kind:5s}: {len(s):4d} flagged | "
                  f"{always:4d} always ({always/len(s):4.0%}) | "
                  f"{new:4d} new-1yr ({new/len(s):4.0%})")


if __name__ == "__main__":
    main()

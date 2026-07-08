import os

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
import folium
from shapely import set_precision

BASE = "/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC"
FLOOD = f"{BASE}/Flood Forecast 6 month/202606FloodForecast_6month.xlsx"
DROUGHT = f"{BASE}/DroughtRiskArea_HII/202606droughtForecast_6month.xlsx"
GEOJSON = f"{BASE}/TH_TAMBON_json/tha_admbnda_adm3_rtsd_20220121_geo.json"

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures", "map")
OUT = os.path.join(HERE, "output", "map")
for d in (FIG, OUT):
    os.makedirs(d, exist_ok=True)

COLORS = {
    "norisk": "#D5D5D5",              # grey
    "flood": "#3964E4",               # blue
    "flashflood": "#E0402F",          # red
    "drought": "#C77B2B",             # amber-brown
    "flood-drought": "#2E8B57",       # green
    "flashflood-drought": "#6B4226",  # brown
}
LABELS = {
    "norisk": "No risk",
    "flood": "Flood",
    "flashflood": "Flash flood",
    "drought": "Drought",
    "flood-drought": "Flood + Drought",
    "flashflood-drought": "Flash flood + Drought",
}
ORDER = ["norisk", "flood", "flashflood", "drought",
         "flood-drought", "flashflood-drought"]
MISSING_COLOR = "#ececec"
MISSING_LABEL = "No data"
EDGE = "#ffffff"
FILL_ALPHA = 0.9

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
          "Oct", "Nov", "Dec"]


def month_label(y, m):
    return f"{MONTHS[m - 1]} {y}"


# ---------------------------------------------------------------- load + merge
print("Reading geometries...")
gdf = gpd.read_file(GEOJSON)
gdf["TAMBON_IDN"] = gdf["ADM3_PCODE"].str[2:].astype(int)
gdf = gdf[["TAMBON_IDN", "ADM1_EN", "ADM2_EN", "ADM3_EN", "geometry"]]


def read_forecast(path, name):
    df = pd.read_excel(path, usecols=["TAMBON_IDN", "TYPE_E", "YEAR", "MONTH"])
    df["TYPE_E"] = df["TYPE_E"].str.strip()
    df = df.drop_duplicates(["TAMBON_IDN", "YEAR", "MONTH"])
    return df.rename(columns={"TYPE_E": name})


print("Reading flood + drought forecasts...")
fl = read_forecast(FLOOD, "flood_type")
dr = read_forecast(DROUGHT, "drought_type")
mrg = fl.merge(dr, on=["TAMBON_IDN", "YEAR", "MONTH"], how="outer")

issue = (int(mrg["YEAR"].min()),
         int(mrg.loc[mrg["YEAR"] == mrg["YEAR"].min(), "MONTH"].min()))
target_months = list(
    mrg[["YEAR", "MONTH"]].drop_duplicates().sort_values(["YEAR", "MONTH"])
    .itertuples(index=False, name=None))


def combine(df):
    """Vectorised flood x drought -> single combined class."""
    f, d = df["flood_type"], df["drought_type"]
    isdr = d.eq("drought")
    return np.select(
        [f.eq("flashflood") & isdr,
         f.eq("flood risk") & isdr,
         f.eq("flashflood"),
         f.eq("flood risk"),
         isdr],
        ["flashflood-drought", "flood-drought", "flashflood", "flood", "drought"],
        default="norisk",
    )


mrg["combined"] = combine(mrg)
issue_lbl = month_label(*issue)
print(f"Forecast issued {issue_lbl}; "
      f"targets: {[month_label(*t) for t in target_months]}")
print("Combined-class totals across all 6 months:")
print(mrg["combined"].value_counts().reindex(ORDER, fill_value=0).to_string())

PRESENT = [k for k in ORDER if (mrg["combined"] == k).any()]
dropped = [LABELS[k] for k in ORDER if k not in PRESENT]
if dropped:
    print("Dropped empty categories from legend:", ", ".join(dropped))


def slice_month(y, m):
    s = mrg[(mrg.YEAR == y) & (mrg.MONTH == m)][["TAMBON_IDN", "combined"]]
    g = gdf.merge(s, on="TAMBON_IDN", how="left")
    g["color"] = g["combined"].map(COLORS).fillna(MISSING_COLOR)
    g["risk"] = g["combined"].map(LABELS).fillna(MISSING_LABEL)
    return g


def lead_of(y, m):
    return (y * 12 + m) - (issue[0] * 12 + issue[1])


# =============================================================== PNG
def plot_month(ax, g, title, counts=True):
    g.plot(ax=ax, color=g["color"], edgecolor=EDGE, linewidth=0.12, alpha=FILL_ALPHA)
    ax.set_axis_off()
    ax.set_title(title, fontsize=12, fontweight="bold")
    if counts:
        vc = g["combined"].value_counts()
        present = [k for k in ORDER if vc.get(k, 0) > 0]
        txt = "\n".join(f"{LABELS[k]}: {int(vc.get(k, 0)):,}" for k in present)
        ax.text(0.02, 0.02, txt, transform=ax.transAxes, fontsize=8,
                va="bottom", ha="left",
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#bbb", alpha=0.85))


legend_handles = [
    Line2D([0], [0], marker="s", color="none", markerfacecolor=COLORS[k],
           markeredgecolor="#999999", markersize=12, label=LABELS[k])
    for k in PRESENT
]

for (y, m) in target_months:
    g = slice_month(y, m)
    fig, ax = plt.subplots(figsize=(8, 10))
    plot_month(ax, g, f"Thailand flood + drought forecast — {month_label(y, m)}\n"
                      f"(issued {issue_lbl}, lead +{lead_of(y, m)}m)")
    ax.legend(handles=legend_handles, loc="upper right", fontsize=8, frameon=True)
    fig.tight_layout()
    fn = os.path.join(FIG, f"map_{y}{m:02d}_lead{lead_of(y, m)}.png")
    fig.savefig(fn, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {os.path.basename(fn)}")

fig, axes = plt.subplots(2, 3, figsize=(18, 22))
for ax, (y, m) in zip(axes.ravel(), target_months):
    plot_month(ax, slice_month(y, m), f"{month_label(y, m)}  (lead +{lead_of(y, m)}m)")
fig.legend(handles=legend_handles, loc="lower center", ncol=3, fontsize=12,
           frameon=True, bbox_to_anchor=(0.5, 0.005))
fig.suptitle(f"HII 6-month flood + drought forecast — issued {issue_lbl}",
             fontsize=18, fontweight="bold", y=0.995)
fig.tight_layout(rect=[0, 0.04, 1, 0.985])
panel = os.path.join(FIG, "map_panel_6month.png")
fig.savefig(panel, dpi=140, bbox_inches="tight")
plt.close(fig)
print(f"  wrote {os.path.basename(panel)}")


print("Building 6-month blended persistence map...")
from matplotlib.colors import to_rgb

rgb_lookup = {k: to_rgb(v) for k, v in COLORS.items()}
miss_rgb = to_rgb(MISSING_COLOR)

wide = mrg.pivot_table(index="TAMBON_IDN", columns=["YEAR", "MONTH"],
                       values="combined", aggfunc="first")


def blend_row(classes):
    rgbs = [rgb_lookup.get(c, miss_rgb) for c in classes if isinstance(c, str)]
    return tuple(np.array(rgbs).mean(axis=0)) if rgbs else miss_rgb


blend = wide.apply(lambda r: blend_row(list(r.values)), axis=1)
n_risk = wide.apply(
    lambda r: int(sum(isinstance(c, str) and c != "norisk" for c in r.values)),
    axis=1)
bdf = pd.DataFrame({"TAMBON_IDN": wide.index,
                    "blend": blend.values, "n_risk": n_risk.values})
gb = gdf.merge(bdf, on="TAMBON_IDN", how="left")
gb["blend"] = gb["blend"].apply(lambda x: x if isinstance(x, tuple) else miss_rgb)
gb["n_risk"] = gb["n_risk"].fillna(0).astype(int)

fig, ax = plt.subplots(figsize=(9, 11))
gb.plot(ax=ax, color=list(gb["blend"]), edgecolor=EDGE, linewidth=0.08)
ax.set_axis_off()
ax.set_title("Thailand flood + drought outlook — 6 months blended\n"
             f"(issued {issue_lbl}, Jun–Nov 2026 combined; "
             "colour = blend of the 6 monthly classes)",
             fontsize=13, fontweight="bold")

ref_handles = [
    Line2D([0], [0], marker="s", color="none", markerfacecolor=COLORS[k],
           markeredgecolor="#999999", markersize=12, label=LABELS[k])
    for k in PRESENT if k != "norisk"]
leg = ax.legend(handles=ref_handles, loc="upper right", fontsize=8,
                frameon=True, title="Hazard (pure = all 6 months)")
leg.get_title().set_fontsize(8)
ax.text(0.02, 0.02,
        "Stronger colour = more months at risk\n"
        "Greyer colour = fewer months at risk\n"
        "Mixed hue = different hazards across months",
        transform=ax.transAxes, fontsize=8, va="bottom", ha="left",
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#bbb", alpha=0.85))
fig.tight_layout()
blendfn = os.path.join(FIG, "map_6month_blend.png")
fig.savefig(blendfn, dpi=160, bbox_inches="tight")
plt.close(fig)
# persistence summary
dist = gb.loc[gb["n_risk"] > 0, "n_risk"].value_counts().sort_index()
print(f"  wrote {os.path.basename(blendfn)}")
print("  tambons by # months at risk (1..6):",
      {int(k): int(v) for k, v in dist.items()})


# =============================================================== folium
print("Building interactive folium map...")
gdf_wgs = gdf.to_crs(4326) if gdf.crs and gdf.crs.to_epsg() != 4326 else gdf
fmap = folium.Map(location=[13.5, 100.8], zoom_start=6,
                  tiles="cartodbpositron", control_scale=True)

gsimp = gdf_wgs.copy()
gsimp["geometry"] = gsimp["geometry"].simplify(0.008, preserve_topology=True)
gsimp["geometry"] = set_precision(gsimp["geometry"].values, 0.001)
gsimp = gsimp[~gsimp["geometry"].is_empty]


def style_by_prop(feat):
    return {"fillColor": feat["properties"]["fill_color"],
            "color": "#ffffff", "weight": 0.25, "fillOpacity": 0.72}


for i, (y, m) in enumerate(target_months):
    s = mrg[(mrg.YEAR == y) & (mrg.MONTH == m)][["TAMBON_IDN", "combined"]]
    g = gsimp.merge(s, on="TAMBON_IDN", how="left")
    g["risk"] = g["combined"].map(LABELS).fillna(MISSING_LABEL)
    g["fill_color"] = g["combined"].map(COLORS).fillna(MISSING_COLOR)
    folium.GeoJson(
        g,
        name=f"{month_label(y, m)} (lead +{lead_of(y, m)}m)",
        style_function=style_by_prop,
        tooltip=folium.GeoJsonTooltip(
            fields=["ADM3_EN", "ADM2_EN", "ADM1_EN", "risk"],
            aliases=["Tambon:", "District:", "Province:", "Risk:"],
            sticky=True),
        show=(i == 0),
    ).add_to(fmap)

folium.LayerControl(collapsed=False).add_to(fmap)

swatches = "".join(
    f'<span style="display:inline-block;width:14px;height:14px;'
    f'background:{COLORS[k]};border:1px solid #999;margin-right:6px;"></span>'
    f'{LABELS[k]}<br>' for k in PRESENT)
swatches += (f'<span style="display:inline-block;width:14px;height:14px;'
             f'background:{MISSING_COLOR};border:1px solid #999;'
             f'margin-right:6px;"></span>{MISSING_LABEL}')
legend_html = (
    '<div style="position: fixed; bottom: 30px; left: 30px; z-index:9999;'
    ' background: white; padding: 10px 14px; border:1px solid #999;'
    ' border-radius:6px; font-size:13px; box-shadow:2px 2px 6px rgba(0,0,0,.3);">'
    '<b>Flood + Drought forecast</b><br>' + swatches + '</div>')
fmap.get_root().html.add_child(folium.Element(legend_html))
title_html = (f'<div style="position: fixed; top: 10px; left: 50%; '
              f'transform: translateX(-50%); z-index:9999; background: white; '
              f'padding: 6px 16px; border:1px solid #999; border-radius:6px; '
              f'font-size:15px; font-weight:bold;">'
              f'HII flood + drought forecast — issued {issue_lbl}</div>')
fmap.get_root().html.add_child(folium.Element(title_html))

html_path = os.path.join(OUT, "flood_drought_map_202606.html")
fmap.save(html_path)
print(f"  wrote {html_path}")
print("\nDone. PNGs in figures/map/ ; HTML in output/map/")

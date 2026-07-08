"""
01_map_forecast.py
------------------
Map the LATEST HII drought forecast (issued 2026-06) onto Thailand tambon
polygons. Mirrors the flood map workflow but for the 2-class drought product.

Produces:
  - PNG choropleths (matplotlib/geopandas) for each of the 6 forecast months
    plus a combined 2x3 panel.
  - An interactive HTML map (folium) with a layer toggle for each of the 6
    forecast months.

Drought classes (TYPE_E):
    norisk   -> no drought risk
    drought  -> drought risk (เสี่ยงแล้ง)

Join: forecast TAMBON_IDN  ==  geojson ADM3_PCODE without the 'TH' prefix.
"""
import os

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
import folium
from shapely import set_precision

FORECAST = ("/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC/"
            "DroughtRiskArea_HII/202606droughtForecast_6month.xlsx")
GEOJSON = ("/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC/"
           "TH_TAMBON_json/tha_admbnda_adm3_rtsd_20220121_geo.json")

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures", "map")
OUT = os.path.join(HERE, "output", "map")
for d in (FIG, OUT):
    os.makedirs(d, exist_ok=True)

# colour + label config -------------------------------------------------------
# Drought palette: grey for no-risk, warm brown-amber for drought.
COLORS = {"norisk": "#D5D5D5", "drought": "#C77B2B"}
LABELS = {"norisk": "No risk", "drought": "Drought risk"}
ORDER = ["norisk", "drought"]
MISSING_COLOR = "#ececec"
MISSING_LABEL = "No data"
EDGE = "#ffffff"
FILL_ALPHA = 0.9

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
          "Oct", "Nov", "Dec"]


def month_label(y, m):
    return f"{MONTHS[m - 1]} {y}"


# ---------------------------------------------------------------- load + join
print("Reading geometries...")
gdf = gpd.read_file(GEOJSON)
gdf["TAMBON_IDN"] = gdf["ADM3_PCODE"].str[2:].astype(int)
gdf = gdf[["TAMBON_IDN", "ADM1_EN", "ADM2_EN", "ADM3_EN", "geometry"]]

print("Reading forecast...")
fc = pd.read_excel(
    FORECAST, usecols=["TAMBON_IDN", "TAMBON_E", "AMPHOE_E", "PROV_E",
                       "TYPE_E", "YEAR", "MONTH"]
)
fc["TYPE_E"] = fc["TYPE_E"].str.strip()
issue = (fc["YEAR"].min(), fc.loc[fc["YEAR"] == fc["YEAR"].min(), "MONTH"].min())

target_months = list(
    fc[["YEAR", "MONTH"]].drop_duplicates().sort_values(["YEAR", "MONTH"])
    .itertuples(index=False, name=None)
)
print(f"Forecast issued {month_label(*issue)}; "
      f"targets: {[month_label(*t) for t in target_months]}")

matched = gdf["TAMBON_IDN"].isin(fc["TAMBON_IDN"]).sum()
print(f"Tambon polygons matched to forecast: {matched} / {len(gdf)}")


def slice_month(y, m):
    s = fc[(fc.YEAR == y) & (fc.MONTH == m)][
        ["TAMBON_IDN", "TYPE_E", "TAMBON_E", "AMPHOE_E", "PROV_E"]]
    g = gdf.merge(s, on="TAMBON_IDN", how="left")
    g["color"] = g["TYPE_E"].map(COLORS).fillna(MISSING_COLOR)
    return g


def lead_of(y, m):
    return (y * 12 + m) - (issue[0] * 12 + issue[1])


# =============================================================== PNG: one map
def plot_month(ax, g, title, counts=True):
    g.plot(ax=ax, color=g["color"], edgecolor=EDGE, linewidth=0.12,
           alpha=FILL_ALPHA)
    ax.set_axis_off()
    ax.set_title(title, fontsize=12, fontweight="bold")
    if counts:
        vc = g["TYPE_E"].value_counts()
        txt = "\n".join(f"{LABELS[k]}: {int(vc.get(k, 0)):,}" for k in ORDER)
        ax.text(0.02, 0.02, txt, transform=ax.transAxes, fontsize=8,
                va="bottom", ha="left",
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#bbb", alpha=0.85))


legend_handles = [
    Line2D([0], [0], marker="s", color="none", markerfacecolor=COLORS[k],
           markeredgecolor="#999999", markersize=12, label=LABELS[k])
    for k in ORDER
]

# --- individual PNG per forecast month ---
for (y, m) in target_months:
    g = slice_month(y, m)
    fig, ax = plt.subplots(figsize=(8, 10))
    plot_month(ax, g, f"Thailand drought forecast — {month_label(y, m)}\n"
                      f"(issued {month_label(*issue)}, lead +{lead_of(y, m)}m)")
    ax.legend(handles=legend_handles, loc="upper right", fontsize=9, frameon=True)
    fig.tight_layout()
    fn = os.path.join(FIG, f"map_{y}{m:02d}_lead{lead_of(y, m)}.png")
    fig.savefig(fn, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {os.path.basename(fn)}")

# --- combined 2x3 panel ---
fig, axes = plt.subplots(2, 3, figsize=(18, 22))
for ax, (y, m) in zip(axes.ravel(), target_months):
    g = slice_month(y, m)
    plot_month(ax, g, f"{month_label(y, m)}  (lead +{lead_of(y, m)}m)")
fig.legend(handles=legend_handles, loc="lower center", ncol=len(ORDER),
           fontsize=12, frameon=True, bbox_to_anchor=(0.5, 0.005))
fig.suptitle(f"HII 6-month drought forecast — issued {month_label(*issue)}",
             fontsize=18, fontweight="bold", y=0.995)
fig.tight_layout(rect=[0, 0.03, 1, 0.985])
panel = os.path.join(FIG, "map_panel_6month.png")
fig.savefig(panel, dpi=140, bbox_inches="tight")
plt.close(fig)
print(f"  wrote {os.path.basename(panel)}")


# =============================================================== HTML: folium
print("Building interactive folium map...")
gdf_wgs = gdf.to_crs(4326) if gdf.crs and gdf.crs.to_epsg() != 4326 else gdf
fmap = folium.Map(location=[13.5, 100.8], zoom_start=6,
                  tiles="cartodbpositron", control_scale=True)

# simplify + round coords so the 6 embedded layers stay light
gsimp = gdf_wgs.copy()
gsimp["geometry"] = gsimp["geometry"].simplify(0.008, preserve_topology=True)
gsimp["geometry"] = set_precision(gsimp["geometry"].values, 0.001)  # ~100 m
gsimp = gsimp[~gsimp["geometry"].is_empty]


def style_by_prop(feat):
    return {"fillColor": feat["properties"]["fill_color"],
            "color": "#ffffff", "weight": 0.25, "fillOpacity": 0.72}


for i, (y, m) in enumerate(target_months):
    g = gsimp.merge(
        fc[(fc.YEAR == y) & (fc.MONTH == m)][
            ["TAMBON_IDN", "TYPE_E", "TAMBON_E", "AMPHOE_E", "PROV_E"]],
        on="TAMBON_IDN", how="left")
    g["risk"] = g["TYPE_E"].map(LABELS).fillna(MISSING_LABEL)
    g["fill_color"] = g["TYPE_E"].map(COLORS).fillna(MISSING_COLOR)
    folium.GeoJson(
        g,
        name=f"{month_label(y, m)} (lead +{lead_of(y, m)}m)",
        style_function=style_by_prop,
        tooltip=folium.GeoJsonTooltip(
            fields=["ADM3_EN", "ADM2_EN", "ADM1_EN", "risk"],
            aliases=["Tambon:", "District:", "Province:", "Drought:"],
            sticky=True),
        show=(i == 0),
    ).add_to(fmap)

folium.LayerControl(collapsed=False).add_to(fmap)

# legend built from the COLORS dict so swatches always match the map
swatches = "".join(
    f'<span style="display:inline-block;width:14px;height:14px;'
    f'background:{COLORS[k]};border:1px solid #999;margin-right:6px;">'
    f'</span>{LABELS[k]}<br>' for k in ORDER
)
swatches += (f'<span style="display:inline-block;width:14px;height:14px;'
             f'background:{MISSING_COLOR};border:1px solid #999;'
             f'margin-right:6px;"></span>{MISSING_LABEL}')
legend_html = (
    '<div style="position: fixed; bottom: 30px; left: 30px; z-index:9999;'
    ' background: white; padding: 10px 14px; border:1px solid #999;'
    ' border-radius:6px; font-size:13px; box-shadow:2px 2px 6px rgba(0,0,0,.3);">'
    '<b>Drought forecast</b><br>' + swatches + '</div>'
)
fmap.get_root().html.add_child(folium.Element(legend_html))
title_html = (f'<div style="position: fixed; top: 10px; left: 50%; '
              f'transform: translateX(-50%); z-index:9999; background: white; '
              f'padding: 6px 16px; border:1px solid #999; border-radius:6px; '
              f'font-size:15px; font-weight:bold;">'
              f'HII 6-month drought forecast — issued {month_label(*issue)}</div>')
fmap.get_root().html.add_child(folium.Element(title_html))

html_path = os.path.join(OUT, "drought_forecast_map_202606.html")
fmap.save(html_path)
print(f"  wrote {html_path}")
print("\nDone. PNGs in figures/map/ ; HTML in output/map/")

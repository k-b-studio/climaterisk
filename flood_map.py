import glob
import json
import os
from pathlib import Path
from datetime import datetime
import folium
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
HERE = Path(__file__).resolve().parent
BASE_OUT_DIR = HERE / "output"
OUT_DIR = BASE_OUT_DIR / TIMESTAMP
OUT_DIR.mkdir(parents=True, exist_ok=True)

LATLONG = Path(
    "/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC/LATLONG.xlsx"
)

# ColorBrewer
REDS = ["#fcbba1", "#fc9272", "#ef3b2c", "#99000d"]
BLUES = ["#c6dbef", "#6baed6", "#2171b5", "#08306b"]


def latest_atrisk_csv() -> str:
    files = glob.glob(str(BASE_OUT_DIR / "*" / "flood_at_risk_areas.csv"))
    if not files:
        files = glob.glob(str(BASE_OUT_DIR / "flood_at_risk_areas.csv"))
    if not files:
        raise FileNotFoundError("Run flood_forecast_analysis.py first.")
    return max(files, key=os.path.getmtime)


def centroids() -> pd.DataFrame:
    ll = pd.read_excel(LATLONG)
    ll["TA_ID"] = ll["TA_ID"].astype(str).str.strip()
    cen = ll.groupby("TA_ID")[["LAT", "LONG"]].mean().reset_index()
    return cen.rename(columns={"TA_ID": "GEOCODE"})


def quartile(series: pd.Series) -> pd.Series:
    """Population quartiles 1..4 (rank-based so ties don't collapse bins)."""
    return pd.qcut(series.rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)


def plot_static(df_atrisk: pd.DataFrame, cen: pd.DataFrame, count_col: str, ramp: list, out_png: Path, title: str):
    """Render a static scatter map using matplotlib."""
    fig, ax = plt.subplots(figsize=(10, 12), dpi=150)

    # Plot all centroids in background
    cen_clean = cen.dropna(subset=["LAT", "LONG"])
    ax.scatter(cen_clean["LONG"], cen_clean["LAT"], s=2, color="#e0e0e0", alpha=0.5)

    sub = df_atrisk[df_atrisk[count_col] > 0].copy()
    if not sub.empty:
        sub["Q"] = quartile(sub[count_col])
        for q in [1, 2, 3, 4]:
            q_sub = sub[sub["Q"] == q]
            if not q_sub.empty:
                ax.scatter(
                    q_sub["LONG"], q_sub["LAT"],
                    s=6 + q * 4, color=ramp[q - 1], alpha=0.8, linewidths=0, label=f"Q{q}"
                )
        ax.legend(title="Quartiles", loc="lower right")

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.set_aspect("equal", adjustable="datalim")

    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved static map -> {out_png}")


def build_layer(fmap, df, count_col, ramp, label):
    """Add one hazard layer (areas with count_col > 0), coloured by quartile."""
    sub = df[df[count_col] > 0].copy()
    sub["Q"] = quartile(sub[count_col])
    fg = folium.FeatureGroup(name=label, show=True)

    # quartile -> count range, for the legend
    ranges = {}
    for q in [1, 2, 3, 4]:
        vals = sub.loc[sub["Q"] == q, count_col]
        ranges[q] = (int(vals.min()), int(vals.max()), len(vals))

    for _, r in sub.iterrows():
        q = int(r["Q"])
        popup = folium.Popup(
            f"<b>{r['TAMBON_E']}</b> ({r['GEOCODE']})<br>"
            f"{r['AMPHOE_E']}, {r['PROV_E']} &mdash; {r['REGION_E']}<br>"
            f"{label} count: <b>{int(r[count_col])}</b> (Q{q})<br>"
            f"flashflood={int(r['N_FLASHFLOOD'])}, flood={int(r['N_FLOOD'])}<br>"
            f"FRAC_ATRISK={r['FRAC_ATRISK']}",
            max_width=260,
        )
        folium.CircleMarker(
            location=[r["LAT"], r["LONG"]],
            radius=3 + q,                 # bigger for higher quartile
            color=ramp[q - 1],
            weight=0.6,
            fill=True,
            fill_color=ramp[q - 1],
            fill_opacity=0.8,
            popup=popup,
        ).add_to(fg)
    fg.add_to(fmap)
    return ranges, len(sub)


def legend_html(ff_ranges, fl_ranges):
    def block(title, ramp, ranges):
        rows = ""
        for q in [4, 3, 2, 1]:
            lo, hi, n = ranges[q]
            rng = f"{lo}" if lo == hi else f"{lo}–{hi}"
            rows += (
                f"<div style='display:flex;align-items:center;margin:2px 0;'>"
                f"<span style='width:14px;height:14px;background:{ramp[q-1]};"
                f"display:inline-block;margin-right:6px;border:1px solid #999;'></span>"
                f"Q{q}: {rng} <span style='color:#777'>(n={n})</span></div>"
            )
        return f"<div style='margin-bottom:8px;'><b>{title}</b>{rows}</div>"

    html = f"""
    <div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:#fff;
        padding:10px 12px;border:1px solid #888;border-radius:6px;font:12px/1.3 sans-serif;
        box-shadow:0 1px 4px rgba(0,0,0,.3);">
      <div style="font-weight:700;margin-bottom:6px;">Forecast count (quartiles)</div>
      {block("Flash flood (red)", REDS, ff_ranges)}
      {block("Flood (blue)", BLUES, fl_ranges)}
      <div style="color:#777;margin-top:4px;">light = Q1 (fewer) &rarr; dark = Q4 (more)</div>
    </div>"""
    return html


def main():
    csv = latest_atrisk_csv()
    print("at-risk source:", csv)
    ar = pd.read_csv(csv, dtype={"GEOCODE": str})
    cen = centroids()

    df = ar.merge(cen, on="GEOCODE", how="left")
    missing = df["LAT"].isna().sum()
    df = df.dropna(subset=["LAT", "LONG"])
    print(f"plotted {len(df)} areas ({missing} dropped, no coordinates)")

    plot_static(df, cen, "N_FLASHFLOOD", REDS, OUT_DIR / f"flood_map_flashflood_{TIMESTAMP}.png", "Flash Flood Areas")
    plot_static(df, cen, "N_FLOOD", BLUES, OUT_DIR / f"flood_map_flood_{TIMESTAMP}.png", "Flood Areas")

    fmap = folium.Map(location=[13.5, 100.9], zoom_start=6, tiles="CartoDB positron")
    ff_ranges, n_ff = build_layer(fmap, df, "N_FLASHFLOOD", REDS, "Flash flood (red)")
    fl_ranges, n_fl = build_layer(fmap, df, "N_FLOOD", BLUES, "Flood (blue)")
    folium.LayerControl(collapsed=False).add_to(fmap)
    fmap.get_root().html.add_child(folium.Element(legend_html(ff_ranges, fl_ranges)))

    out_html = OUT_DIR / "flood_map.html"
    fmap.save(str(out_html))

    pts = []
    for kind, col, ramp in [("flashflood", "N_FLASHFLOOD", REDS), ("flood", "N_FLOOD", BLUES)]:
        sub = df[df[col] > 0].copy()
        sub["Q"] = quartile(sub[col])
        for _, r in sub.iterrows():
            pts.append({
                "lat": round(float(r["LAT"]), 3), "lon": round(float(r["LONG"]), 3),
                "kind": kind, "q": int(r["Q"]), "n": int(r[col]),
                "name": r["TAMBON_E"], "prov": r["PROV_E"],
            })
    (OUT_DIR / "flood_map_points.json").write_text(json.dumps(pts))

    print(f"\nFlash flood (red): {n_ff} areas  quartile ranges {ff_ranges}")
    print(f"Flood (blue):      {n_fl} areas  quartile ranges {fl_ranges}")
    print(f"\nMap : {out_html}")
    print(f"JSON: {OUT_DIR/'flood_map_points.json'} ({len(pts)} points)")


if __name__ == "__main__":
    main()

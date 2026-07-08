import json
import re
from datetime import datetime
from pathlib import Path

import folium
import matplotlib.pyplot as plt
import pandas as pd

# --- Configuration ---
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(
    "/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC/Flood Forecast 6 month"
)
LATLONG_PATH = Path(
    "/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC/CodeTAMBON.xlsx"
)
METADATA_PATH = DATA_DIR / "metadata.xlsx"

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR = PROJECT_DIR / "output" / TIMESTAMP

KEEP_COLS = ["GEOCODE", "TYPE_E", "YEAR", "MONTH"]
RISK_MAP = {"norisk": 0, "flashflood": 1, "inundation": 2, "flood risk": 2}
RISK_LABEL = {0: "no risk", 1: "flashflood", 2: "flood / inundation"}
META_COLS = ["GEOCODE", "TAMBON_E", "AMPHOE_E", "PROV_E", "REGION_E"]

MIN_FRAC_ATRISK = 0.1

# ColorBrewer
REDS = ["#fcbba1", "#fc9272", "#ef3b2c", "#99000d"]
BLUES = ["#c6dbef", "#6baed6", "#2171b5", "#08306b"]

MAP_CENTER = [13.5, 100.9]  # Thailand


def normalize_geocode(s: pd.Series) -> pd.Series:
    """
    """
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def parse_issue(filename: str) -> str:
    """Extract the YYYYMM issue month from a forecast filename."""
    m = re.match(r"(\d{6})", filename)
    if not m:
        raise ValueError(f"Cannot parse issue month (YYYYMM) from filename: {filename}")
    return m.group(1)


# 1. load
def load_forecasts() -> pd.DataFrame:
    # Exclude Excel lock files (~$...) that match the glob when a file is open
    files = sorted(
        f for f in DATA_DIR.glob("*FloodForecast_6month.xlsx")
        if not f.name.startswith("~$")
    )
    if not files:
        raise FileNotFoundError(f"No forecast files found in {DATA_DIR}")

    frames = []
    for f in files:
        issue = parse_issue(f.name)  # e.g. '202401'
        raw = pd.read_excel(f)
        if "GEOCODE" not in raw.columns:
            if "TAMBON_IDN" not in raw.columns:
                # Skipping a file would silently bias FRAC_ATRISK denominators
                raise ValueError(f"{f.name}: neither GEOCODE nor TAMBON_IDN column found")
            raw["GEOCODE"] = raw["TAMBON_IDN"]
        missing_cols = [c for c in KEEP_COLS if c not in raw.columns]
        if missing_cols:
            raise ValueError(f"{f.name}: missing expected columns {missing_cols}")

        df = raw[KEEP_COLS].copy()
        df["ISSUE"] = issue
        frames.append(df)
        print(f"  loaded {f.name:42s} rows={len(df):>7,}")

    combined = pd.concat(frames, ignore_index=True)
    print(f"  -> combined rows: {len(combined):,} from {len(files)} files")
    return combined


# 2. recode
def recode(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["TYPE_E"] = df["TYPE_E"].astype(str).str.strip().str.lower()
    unknown = set(df["TYPE_E"].unique()) - set(RISK_MAP)
    if unknown:
        raise ValueError(f"Unexpected TYPE_E values: {unknown}")
    df["RISK_CODE"] = df["TYPE_E"].map(RISK_MAP).astype("int8")
    df["GEOCODE"] = normalize_geocode(df["GEOCODE"])
    return df


# 3. at-risk areas
def at_risk_summary(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    atrisk = df[df["RISK_CODE"] >= 1].copy()  # flashflood or inundation only
    atrisk["TARGET_MONTH"] = (
        atrisk["YEAR"].astype(str) + "-" + atrisk["MONTH"].astype(str).str.zfill(2)
    )

    summary = (
        atrisk.assign(
            IS_FLASHFLOOD=atrisk["RISK_CODE"].eq(1),
            IS_FLOOD=atrisk["RISK_CODE"].eq(2),
        )
        .groupby("GEOCODE")
        .agg(
            N_FLASHFLOOD=("IS_FLASHFLOOD", "sum"),
            N_FLOOD=("IS_FLOOD", "sum"),
            N_ATRISK_RECORDS=("RISK_CODE", "size"),
            MAX_SEVERITY=("RISK_CODE", "max"),
            ISSUES_FLAGGED=("ISSUE", lambda s: ", ".join(sorted(s.unique()))),
            N_ISSUES_FLAGGED=("ISSUE", "nunique"),
            TARGET_MONTHS=("TARGET_MONTH", lambda s: ", ".join(sorted(s.unique()))),
        )
        .reset_index()
    )

    # total forecast records seen per GEOCODE/TAMBON
    totals = df.groupby("GEOCODE").size().rename("N_TOTAL_RECORDS")
    summary = summary.merge(totals, on="GEOCODE", how="left")
    summary["FRAC_ATRISK"] = (summary["N_ATRISK_RECORDS"] / summary["N_TOTAL_RECORDS"]).round(3)
    summary["MAX_SEVERITY_LABEL"] = summary["MAX_SEVERITY"].map(RISK_LABEL)

    flagged = summary[summary["FRAC_ATRISK"] >= MIN_FRAC_ATRISK].copy()
    flagged = flagged.sort_values(
        ["N_FLOOD", "N_FLASHFLOOD", "N_ATRISK_RECORDS"], ascending=False
    ).reset_index(drop=True)
    return flagged, atrisk


# 4. metadata
def load_metadata() -> pd.DataFrame:
    md = pd.read_excel(METADATA_PATH)
    md["GEOCODE"] = normalize_geocode(md["GEOCODE"])
    md = md[[c for c in META_COLS if c in md.columns]].drop_duplicates("GEOCODE")
    return md


def join_metadata(summary: pd.DataFrame, md: pd.DataFrame) -> pd.DataFrame:
    out = summary.merge(md, on="GEOCODE", how="left")

    name_cols = [c for c in md.columns if c != "GEOCODE"]
    metric_cols = [
        "MAX_SEVERITY_LABEL", "N_FLASHFLOOD", "N_FLOOD", "N_ATRISK_RECORDS",
        "N_TOTAL_RECORDS", "FRAC_ATRISK", "N_ISSUES_FLAGGED", "ISSUES_FLAGGED",
        "TARGET_MONTHS",
    ]
    out = out[["GEOCODE"] + name_cols + metric_cols]
    return out


# 5. export
def export(summary: pd.DataFrame, atrisk_records: pd.DataFrame, md: pd.DataFrame):
    flagged_geos = set(summary["GEOCODE"])
    detail = atrisk_records[atrisk_records["GEOCODE"].isin(flagged_geos)].copy()
    detail["RISK_LABEL"] = detail["RISK_CODE"].map(RISK_LABEL)
    detail = detail.merge(md, on="GEOCODE", how="left")

    name_cols = [c for c in md.columns if c != "GEOCODE"]
    detail = detail[
        ["GEOCODE"] + name_cols
        + ["ISSUE", "YEAR", "MONTH", "TYPE_E", "RISK_CODE", "RISK_LABEL"]
    ].sort_values(["GEOCODE", "ISSUE"]).reset_index(drop=True)

    legend = pd.DataFrame({
        "TYPE_E (raw)": ["norisk", "flashflood", "inundation", "flood risk"],
        "RISK_CODE": [0, 1, 2, 2],
        "MEANING": ["no risk", "flash flood",
                    "flood/inundation (label used 202401-202405)",
                    "flood/inundation (label used 202406 onward)"],
    })
    notes = pd.DataFrame({"NOTE": [
        "Dataset: IECC Flood Forecast 6-month, 30 monthly files 202401..202606 + metadata.xlsx.",
        "Each file is a rolling 6-month forecast; YEAR/MONTH = forecast TARGET month; ISSUE = file month.",
        "Columns kept from forecasts: GEOCODE, TYPE_E, YEAR, MONTH (+ ISSUE for traceability).",
        "TYPE_E recoded to RISK_CODE: norisk=0, flashflood=1, inundation/flood risk=2.",
        "The code-2 flood class was relabelled mid-series (inundation 202401-202405; flood risk after); both mean code 2.",
        f"AT-RISK rule: GEOCODE with FRAC_ATRISK >= {MIN_FRAC_ATRISK} (flashflood/flood in >= {MIN_FRAC_ATRISK:.0%} of its forecasts).",
        "NOTE: rolling forecasts overlap, so a target month can be counted in up to 6 issues; "
        "FRAC_ATRISK therefore weights persistent signals, not distinct events.",
        "Only at-risk areas are exported. Metadata (names/region) joined on GEOCODE.",
        "AtRisk_Areas = one row per area (summary). AtRisk_Records = the underlying flashflood/inundation rows.",
    ]})

    xlsx = OUT_DIR / "flood_at_risk_areas.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        notes.to_excel(xw, sheet_name="ReadMe", index=False)
        legend.to_excel(xw, sheet_name="ReadMe", index=False, startrow=len(notes) + 2)
        summary.to_excel(xw, sheet_name="AtRisk_Areas", index=False)
        detail.to_excel(xw, sheet_name="AtRisk_Records", index=False)

    summary.to_csv(OUT_DIR / "flood_at_risk_areas.csv", index=False)
    detail.to_csv(OUT_DIR / "flood_at_risk_records.csv", index=False)
    return xlsx, detail


# 6. maps
def centroids() -> pd.DataFrame:
    ll = pd.read_excel(LATLONG_PATH)
    ll["TAMBON_IDN"] = normalize_geocode(ll["TAMBON_IDN"])
    cen = ll.groupby("TAMBON_IDN")[["LATITUDE_CENTER_TAMBON", "LONGITUDE_CENTER_TAMBON"]].mean().reset_index()
    return cen.rename(columns={"TAMBON_IDN": "GEOCODE"})


def quartile(series: pd.Series) -> pd.Series:
    """Population quartiles 1..4 (rank-based so ties don't collapse bins).

    Falls back to fewer bins (or a single bin) when there are fewer than
    4 values, instead of letting pd.qcut raise.
    """
    bins = min(4, len(series))
    if bins < 2:
        return pd.Series(1, index=series.index, dtype=int)
    return pd.qcut(series.rank(method="first"), bins, labels=range(1, bins + 1)).astype(int)


def with_quartiles(df: pd.DataFrame, count_col: str) -> pd.DataFrame:
    """Areas with count_col > 0, with a quartile column Q added."""
    sub = df[df[count_col] > 0].copy()
    if not sub.empty:
        sub["Q"] = quartile(sub[count_col])
    return sub


def plot_static(df_atrisk: pd.DataFrame, cen: pd.DataFrame, count_col: str,
                ramp: list, out_png: Path, title: str):
    """Render a static scatter map using matplotlib."""
    fig, ax = plt.subplots(figsize=(10, 12), dpi=150)

    # Plot all centroids in background
    cen_clean = cen.dropna(subset=["LATITUDE_CENTER_TAMBON", "LONGITUDE_CENTER_TAMBON"])
    ax.scatter(cen_clean["LONGITUDE_CENTER_TAMBON"], cen_clean["LATITUDE_CENTER_TAMBON"], s=2, color="#e0e0e0", alpha=0.5)

    sub = with_quartiles(df_atrisk, count_col)
    for q, q_sub in sub.groupby("Q"):
        ax.scatter(
            q_sub["LONGITUDE_CENTER_TAMBON"], q_sub["LATITUDE_CENTER_TAMBON"],
            s=6 + q * 4, color=ramp[q - 1], alpha=0.8, linewidths=0, label=f"Q{q}"
        )
    if not sub.empty:
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
    sub = with_quartiles(df, count_col)
    fg = folium.FeatureGroup(name=label, show=True)

    # quartile -> count range, for the legend
    ranges = {}
    for q, vals in sub.groupby("Q")[count_col]:
        ranges[int(q)] = (int(vals.min()), int(vals.max()), len(vals))

    for r in sub.itertuples():
        q = int(r.Q)
        popup = folium.Popup(
            f"<b>{r.TAMBON_E}</b> ({r.GEOCODE})<br>"
            f"{r.AMPHOE_E}, {r.PROV_E} &mdash; {r.REGION_E}<br>"
            f"{label} count: <b>{int(getattr(r, count_col))}</b> (Q{q})<br>"
            f"flashflood={int(r.N_FLASHFLOOD)}, flood={int(r.N_FLOOD)}<br>"
            f"FRAC_ATRISK={r.FRAC_ATRISK}",
            max_width=260,
        )
        folium.CircleMarker(
            location=[r.LATITUDE_CENTER_TAMBON, r.LONGITUDE_CENTER_TAMBON],
            radius=3 + q,
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
        for q in sorted(ranges, reverse=True):
            lo, hi, n = ranges[q]
            rng = f"{lo}" if lo == hi else f"{lo}-{hi}"
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


def export_points_json(dfm: pd.DataFrame):
    pts = []
    for kind, col in [("flashflood", "N_FLASHFLOOD"), ("flood", "N_FLOOD")]:
        sub = with_quartiles(dfm, col)
        for r in sub.itertuples():
            pts.append({
                "lat": round(float(r.LATITUDE_CENTER_TAMBON), 3), "lon": round(float(r.LONGITUDE_CENTER_TAMBON), 3),
                "kind": kind, "q": int(r.Q), "n": int(getattr(r, col)),
                "name": r.TAMBON_E, "prov": r.PROV_E,
            })
    out_json = OUT_DIR / "flood_map_points.json"
    out_json.write_text(json.dumps(pts))
    print(f"JSON: {out_json} ({len(pts)} points)")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Output dir:", OUT_DIR)

    print("1) Loading forecast files ...")
    raw = load_forecasts()
    print("2) Recoding TYPE_E -> RISK_CODE ...")
    df = recode(raw)
    print("3) Building at-risk summary ...")
    summary, atrisk_records = at_risk_summary(df)
    print("4) Joining metadata ...")
    md = load_metadata()
    summary = join_metadata(summary, md)
    print("5) Exporting ...")
    xlsx, detail = export(summary, atrisk_records, md)

    total_areas = df["GEOCODE"].nunique()
    ever = atrisk_records["GEOCODE"].nunique()
    print("================= RESULT =================")
    print(f"Distinct areas (GEOCODE) in data ........ {total_areas:,}")
    print(f"Areas flagged at least once ............. {ever:,}")
    print(f"Areas flagged FRAC_ATRISK >= {MIN_FRAC_ATRISK:.0%} (EXPORTED) ... {len(summary):,}")
    print(f"  - with any flood/inundation forecast .. {(summary['N_FLOOD'] > 0).sum():,}")
    print(f"  - flashflood only ..................... {(summary['N_FLOOD'] == 0).sum():,}")
    print(f"At-risk detail records exported ......... {len(detail):,}")
    print(f"\nWorkbook : {xlsx}")
    print(f"CSVs     : {OUT_DIR}/flood_at_risk_areas.csv , flood_at_risk_records.csv")
    print("\nTop 10 areas by flood then flashflood count:")
    cols = ["GEOCODE", "TAMBON_E", "AMPHOE_E", "PROV_E", "REGION_E",
            "N_FLASHFLOOD", "N_FLOOD", "N_ATRISK_RECORDS"]
    print(summary[cols].head(10).to_string(index=False))

    print("6) Building maps ...")
    cen = centroids()
    dfm = summary.merge(cen, on="GEOCODE", how="left")
    missing = dfm["LATITUDE_CENTER_TAMBON"].isna().sum()
    dfm = dfm.dropna(subset=["LATITUDE_CENTER_TAMBON", "LONGITUDE_CENTER_TAMBON"])
    print(f"plotted {len(dfm)} areas ({missing} dropped, no coordinates)")

    plot_static(dfm, cen, "N_FLASHFLOOD", REDS,
                OUT_DIR / f"flood_map_flashflood_{TIMESTAMP}.png", "Flash Flood Areas")
    plot_static(dfm, cen, "N_FLOOD", BLUES,
                OUT_DIR / f"flood_map_flood_{TIMESTAMP}.png", "Flood Areas")

    fmap = folium.Map(location=MAP_CENTER, zoom_start=6, tiles="CartoDB positron")
    ff_ranges, n_ff = build_layer(fmap, dfm, "N_FLASHFLOOD", REDS, "Flash flood (red)")
    fl_ranges, n_fl = build_layer(fmap, dfm, "N_FLOOD", BLUES, "Flood (blue)")
    folium.LayerControl(collapsed=False).add_to(fmap)
    fmap.get_root().html.add_child(folium.Element(legend_html(ff_ranges, fl_ranges)))

    out_html = OUT_DIR / "flood_map.html"
    fmap.save(str(out_html))

    print(f"Flash flood (red): {n_ff} areas  quartile ranges {ff_ranges}")
    print(f"Flood (blue):      {n_fl} areas  quartile ranges {fl_ranges}")
    print(f"Map : {out_html}")

    export_points_json(dfm)


if __name__ == "__main__":
    main()

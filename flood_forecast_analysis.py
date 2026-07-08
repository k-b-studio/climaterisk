import re
from datetime import datetime
from 
hlib import Path
import pandas as pd

# ---------------------------------------------------------------- config
DATA_DIR = Path(
    "/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC/Flood Forecast 6 month"
)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR = Path(__file__).resolve().parent / "output" / TIMESTAMP
OUT_DIR.mkdir(parents=True, exist_ok=True)

KEEP_COLS = ["GEOCODE", "TYPE_E", "YEAR", "MONTH"]
RISK_MAP = {"norisk": 0, "flashflood": 1, "inundation": 2, "flood risk": 2}
RISK_LABEL = {0: "no risk", 1: "flashflood", 2: "flood / inundation"}

MIN_FRAC_ATRISK = 0.2

# 1. load ---------------------------------------------------------------- 
def load_forecasts() -> pd.DataFrame:
    files = sorted(DATA_DIR.glob("*FloodForecast_6month.xlsx"))
    if not files:
        raise FileNotFoundError(f"No forecast files found in {DATA_DIR}")

    frames = []
    for f in files:
        issue = re.match(r"(\d{6})", f.name).group(1)  # e.g. '202401'
        raw = pd.read_excel(f)
        if "GEOCODE" not in raw.columns:
            raw["GEOCODE"] = raw["TAMBON_IDN"]
        df = raw[KEEP_COLS].copy()
        df["ISSUE"] = issue
        frames.append(df)
        print(f"  loaded {f.name:42s} rows={len(df):>7,}")

    combined = pd.concat(frames, ignore_index=True)
    print(f"  -> combined rows: {len(combined):,} from {len(files)} files")
    return combined


# 2. recode ---------------------------------------------------------------- 
def recode(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["TYPE_E"] = df["TYPE_E"].astype(str).str.strip().str.lower()
    unknown = set(df["TYPE_E"].unique()) - set(RISK_MAP)
    if unknown:
        raise ValueError(f"Unexpected TYPE_E values: {unknown}")
    df["RISK_CODE"] = df["TYPE_E"].map(RISK_MAP).astype("int8")
    df["GEOCODE"] = df["GEOCODE"].astype(str).str.strip()
    return df


# 3. at-risk areas ---------------------------------------------------------------- 
def at_risk_summary(df: pd.DataFrame) -> pd.DataFrame:
    atrisk = df[df["RISK_CODE"] >= 1]  # flashflood or inundation only

    g = atrisk.groupby("GEOCODE")
    summary = pd.DataFrame({
        "N_FLASHFLOOD": g.apply(lambda x: (x["RISK_CODE"] == 1).sum(), include_groups=False),
        "N_FLOOD": g.apply(lambda x: (x["RISK_CODE"] == 2).sum(), include_groups=False),
        "N_ATRISK_RECORDS": g.size(),
        "MAX_SEVERITY": g["RISK_CODE"].max(),
        "ISSUES_FLAGGED": g["ISSUE"].apply(lambda s: ", ".join(sorted(s.unique()))),
        "N_ISSUES_FLAGGED": g["ISSUE"].nunique(),
        "TARGET_MONTHS": g.apply(
            lambda x: ", ".join(sorted({f"{y}-{m:02d}" for y, m in zip(x["YEAR"], x["MONTH"])})),
            include_groups=False,
        ),
    }).reset_index()

    # total forecast records seen per GEOCODE
    totals = df.groupby("GEOCODE").size().rename("N_TOTAL_RECORDS")
    summary = summary.merge(totals, on="GEOCODE", how="left")
    summary["FRAC_ATRISK"] = (summary["N_ATRISK_RECORDS"] / summary["N_TOTAL_RECORDS"]).round(3)
    summary["MAX_SEVERITY_LABEL"] = summary["MAX_SEVERITY"].map(RISK_LABEL)

    flagged = summary[summary["FRAC_ATRISK"] >= MIN_FRAC_ATRISK].copy()
    flagged = flagged.sort_values(
        ["N_FLOOD", "N_FLASHFLOOD", "N_ATRISK_RECORDS"], ascending=False
    ).reset_index(drop=True)
    return flagged, atrisk


# 4. metadata join ---------------------------------------------------------------- 
def join_metadata(summary: pd.DataFrame) -> pd.DataFrame:
    md = pd.read_excel(DATA_DIR / "metadata.xlsx")
    md["GEOCODE"] = md["GEOCODE"].astype(str).str.strip()
    meta_cols = [
        "GEOCODE", "TAMBON_E", "AMPHOE_E",
        "PROV_E", "REGION_E",
    ]
    md = md[[c for c in meta_cols if c in md.columns]].drop_duplicates("GEOCODE")
    out = summary.merge(md, on="GEOCODE", how="left")

    # tidy column order: keys + names first, metrics after
    name_cols = [c for c in meta_cols if c in out.columns and c != "GEOCODE"]
    metric_cols = [
        "MAX_SEVERITY_LABEL", "N_FLASHFLOOD", "N_FLOOD", "N_ATRISK_RECORDS",
        "N_TOTAL_RECORDS", "FRAC_ATRISK", "N_ISSUES_FLAGGED", "ISSUES_FLAGGED",
        "TARGET_MONTHS",
    ]
    out = out[["GEOCODE"] + name_cols + metric_cols]
    return out


# 5. export ----------------------------------------------------------------
def export(summary: pd.DataFrame, atrisk_records: pd.DataFrame):
    flagged_geos = set(summary["GEOCODE"])
    detail = atrisk_records[atrisk_records["GEOCODE"].isin(flagged_geos)].copy()
    detail["RISK_LABEL"] = detail["RISK_CODE"].map(RISK_LABEL)
    md = pd.read_excel(DATA_DIR / "metadata.xlsx")
    md["GEOCODE"] = md["GEOCODE"].astype(str).str.strip()
    detail = detail.merge(
        md[["GEOCODE", "TAMBON_E", "AMPHOE_E", "PROV_E", "REGION_E"]].drop_duplicates("GEOCODE"),
        on="GEOCODE", how="left",
    )
    detail = detail[[
        "GEOCODE", "TAMBON_E", "AMPHOE_E", "PROV_E", "REGION_E",
        "ISSUE", "YEAR", "MONTH", "TYPE_E", "RISK_CODE", "RISK_LABEL",
    ]].sort_values(["GEOCODE", "ISSUE"]).reset_index(drop=True)

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


# main ---------------------------------------------------------------- 
def main():
    print("1) Loading 30 forecast files ...")
    raw = load_forecasts()
    print("2) Recoding TYPE_E -> RISK_CODE ...")
    df = recode(raw)
    print("3) Building at-risk summary (>= 2 records) ...")
    summary, atrisk_records = at_risk_summary(df)
    print("4) Joining metadata ...")
    summary = join_metadata(summary)
    print("5) Exporting ...")
    xlsx, detail = export(summary, atrisk_records)

    # console report ----- 
    total_areas = df["GEOCODE"].nunique()
    ever = atrisk_records["GEOCODE"].nunique()
    print("\n================= RESULT =================")
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


if __name__ == "__main__":
    main()

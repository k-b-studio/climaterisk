import re
from datetime import datetime
from pathlib import Path

import pandas as pd

# --- Configuration ---
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(
    "/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC/Flood Forecast 6 month"
)
LATLONG_PATH = Path(
    "/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC/LATLONG.xlsx"
)
METADATA_PATH = DATA_DIR / "metadata.xlsx"

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR = PROJECT_DIR / "output" / f"validation_{TIMESTAMP}"

KEEP_COLS = ["GEOCODE", "TYPE_E", "YEAR", "MONTH"]


def normalize_geocode(s: pd.Series) -> pd.Series:
    """Normalize join keys read from Excel: string, stripped, no float artifact.

    If a key column contains any blank cell, pandas reads it as float64 and
    astype(str) turns every key into e.g. '320101.0', silently breaking joins.
    """
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def parse_issue(filename: str) -> str:
    """Extract the YYYYMM issue month from a forecast filename."""
    m = re.match(r"(\d{6})", filename)
    if not m:
        raise ValueError(f"Cannot parse issue month (YYYYMM) from filename: {filename}")
    return m.group(1)


def load_forecasts(data_dir: Path) -> pd.DataFrame:
    """Loads and concatenates all 6-month flood forecast Excel files."""
    # Exclude Excel lock files (~$...) that match the glob when a file is open
    files = sorted(
        f for f in data_dir.glob("*FloodForecast_6month.xlsx")
        if not f.name.startswith("~$")
    )
    if not files:
        raise FileNotFoundError(f"No forecast files found in {data_dir}")

    frames = []
    print(f"Loading {len(files)} forecast files from: {data_dir}")
    for f in files:
        issue = parse_issue(f.name)  # e.g. '202401'
        raw = pd.read_excel(f)
        if "GEOCODE" not in raw.columns:
            # Handle legacy column name
            if "TAMBON_IDN" in raw.columns:
                raw["GEOCODE"] = raw["TAMBON_IDN"]
            else:
                print(f"  [Warning] GEOCODE and TAMBON_IDN not found in {f.name}, skipped")
                continue

        missing_cols = [c for c in KEEP_COLS if c not in raw.columns]
        if missing_cols:
            print(f"  [Warning] {f.name} missing columns {missing_cols}, skipped")
            continue

        df = raw[KEEP_COLS].copy()
        df["ISSUE"] = issue
        frames.append(df)
        print(f"  - Loaded {f.name:42s} rows={len(df):>7,}")

    if not frames:
        raise ValueError("No data loaded from forecast files.")

    combined = pd.concat(frames, ignore_index=True)
    combined["GEOCODE"] = normalize_geocode(combined["GEOCODE"])
    print(f"  -> Combined forecast rows: {len(combined):,}")
    return combined


def load_metadata(metadata_path: Path) -> pd.DataFrame:
    """Loads metadata and prepares GEOCODE column."""
    print(f"Loading metadata from: {metadata_path}")
    md = pd.read_excel(metadata_path)
    md["GEOCODE"] = normalize_geocode(md["GEOCODE"])
    return md


def load_latlong(latlong_path: Path) -> pd.DataFrame:
    """Loads lat/long data and renames TA_ID to GEOCODE."""
    print(f"Loading lat/long data from: {latlong_path}")
    ll = pd.read_excel(latlong_path)
    ll["TA_ID"] = normalize_geocode(ll["TA_ID"])
    ll = ll.rename(columns={"TA_ID": "GEOCODE"})
    return ll


def main():
    """Main script to run data validation."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUT_DIR}\n")

    # 1. Load all data sources
    forecast_df = load_forecasts(DATA_DIR)
    metadata_df = load_metadata(METADATA_PATH)
    latlong_df = load_latlong(LATLONG_PATH)

    # 2. Get unique GEOCODEs from each source
    forecast_geocodes = set(forecast_df["GEOCODE"].unique())
    metadata_geocodes = set(metadata_df["GEOCODE"].unique())
    latlong_geocodes = set(latlong_df["GEOCODE"].unique())

    # 3. Find GEOCODEs in forecasts that are missing from other files
    missing_in_metadata = forecast_geocodes - metadata_geocodes
    missing_in_latlong = forecast_geocodes - latlong_geocodes
    problematic_geocodes = sorted(missing_in_metadata | missing_in_latlong)

    # Duplicate metadata keys: the analysis pipeline keeps the first row per
    # GEOCODE (drop_duplicates), so any duplicate here is a silent choice
    n_dup_metadata = int(metadata_df["GEOCODE"].duplicated().sum())
    # (duplicate TA_IDs in LATLONG are expected: point-level data, centroided later)

    # 4. Create a summary report
    total_forecast_geocodes = len(forecast_geocodes)
    pct_missing_metadata = (
        len(missing_in_metadata) / total_forecast_geocodes * 100
    ) if total_forecast_geocodes > 0 else 0
    pct_missing_latlong = (
        len(missing_in_latlong) / total_forecast_geocodes * 100
    ) if total_forecast_geocodes > 0 else 0

    summary_data = {
        "Metric": [
            "Total Unique GEOCODEs in Forecasts",
            "GEOCODEs in Forecasts but missing in metadata.xlsx",
            "% Missing in metadata.xlsx",
            "GEOCODEs in Forecasts but missing in LATLONG.xlsx",
            "% Missing in LATLONG.xlsx",
            "Duplicate GEOCODE rows in metadata.xlsx",
            "Total GEOCODEs with issues (exported)",
        ],
        "Value": [
            f"{total_forecast_geocodes:,}",
            f"{len(missing_in_metadata):,}",
            f"{pct_missing_metadata:.2f}%",
            f"{len(missing_in_latlong):,}",
            f"{pct_missing_latlong:.2f}%",
            f"{n_dup_metadata:,}",
            f"{len(problematic_geocodes):,}",
        ],
    }
    summary_df = pd.DataFrame(summary_data)

    print("\n--- Validation Summary ---")
    print(summary_df.to_string(index=False))

    # 5. Create a detailed report of problematic GEOCODEs
    issue_df = pd.DataFrame({"GEOCODE": problematic_geocodes})
    issue_df["missing_in_metadata"] = issue_df["GEOCODE"].isin(missing_in_metadata)
    issue_df["missing_in_latlong"] = issue_df["GEOCODE"].isin(missing_in_latlong)

    # Find which forecast files (issues) the problematic GEOCODEs appeared in
    problematic_forecasts = forecast_df[forecast_df["GEOCODE"].isin(problematic_geocodes)]
    issues_flagged = (
        problematic_forecasts.groupby("GEOCODE")["ISSUE"]
        .apply(lambda s: ", ".join(sorted(s.unique())))
        .rename("forecast_files_appeared_in")
    )
    issue_df = issue_df.merge(issues_flagged, on="GEOCODE", how="left")

    # 6. Export to Excel
    output_xlsx = OUT_DIR / "data_validation_report.xlsx"
    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        issue_df.to_excel(writer, sheet_name="Problematic_GEOCODEs", index=False)

    print(f"\nSuccessfully created validation report: {output_xlsx}")


if __name__ == "__main__":
    main()

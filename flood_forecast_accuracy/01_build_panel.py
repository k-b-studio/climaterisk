
import glob
import os
import re

import pandas as pd

SRC = "/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC/Flood Forecast 6 month"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

# canonical class order / severity ranking
CLASS_ORDER = ["norisk", "flood risk", "flashflood"]
SEVERITY = {"norisk": 0, "flood risk": 1, "flashflood": 2}


def ym_to_index(year, month):
    """Calendar month -> integer month index (months since year 0)."""
    return year * 12 + (month - 1)


def index_to_label(idx):
    y, m = divmod(idx, 12)
    return f"{y}-{m + 1:02d}"


def load_panel():
    files = sorted(glob.glob(os.path.join(SRC, "2*FloodForecast_6month.xlsx")))
    frames = []
    for f in files:
        y, m = re.match(r"(\d{4})(\d{2})", os.path.basename(f)).groups()
        issue_idx = ym_to_index(int(y), int(m))
        df = pd.read_excel(
            f, usecols=["TAMBON_IDN", "PROV_CODE", "YEAR", "MONTH", "TYPE_E"]
        )
        df["issue_idx"] = issue_idx
        df["target_idx"] = ym_to_index(df["YEAR"], df["MONTH"])
        df["lead"] = df["target_idx"] - df["issue_idx"]
        frames.append(df)
        print(f"  loaded {os.path.basename(f)}: {len(df):,} rows")
    panel = pd.concat(frames, ignore_index=True)
    panel["TYPE_E"] = panel["TYPE_E"].str.strip()
    return panel


def add_region(panel):
    meta = pd.read_excel(
        os.path.join(SRC, "metadata.xlsx"),
        usecols=["GEOCODE", "PROV_E", "REGION_E", "REGION"],
    ).rename(columns={"GEOCODE": "TAMBON_IDN"})
    meta = meta.drop_duplicates("TAMBON_IDN")
    return panel.merge(meta, on="TAMBON_IDN", how="left")


def build_verification_table(panel):
    wide = panel.pivot_table(
        index=["target_idx", "TAMBON_IDN", "PROV_E", "REGION_E", "REGION"],
        columns="lead",
        values="TYPE_E",
        aggfunc="first",
    )
    wide.columns = [f"lead_{c}" for c in wide.columns]
    wide = wide.reset_index()
    return wide


def main():
    print("Loading forecast files...")
    panel = load_panel()
    panel = add_region(panel)
    panel.to_csv(os.path.join(DATA, "forecast_panel.csv"), index=False)
    print(f"Panel saved: {len(panel):,} rows")

    vt = build_verification_table(panel)
    vt["target_label"] = vt["target_idx"].apply(index_to_label)
    vt.to_csv(os.path.join(DATA, "verification_table.csv"), index=False)
    print(f"Verification table saved: {len(vt):,} rows, cols={list(vt.columns)}")

    # quick coverage report: which target months have a lead-0 (reporting) file
    has0 = vt.dropna(subset=["lead_0"])
    cov = (
        has0.groupby("target_label")[[f"lead_{i}" for i in range(6)]]
        .apply(lambda d: d.notna().all().sum())
    )
    print("\nLead coverage per target month (n leads available, max 6):")
    print(cov.to_string())


if __name__ == "__main__":
    main()

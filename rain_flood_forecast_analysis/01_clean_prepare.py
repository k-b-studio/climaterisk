# -*- coding: utf-8 -*-
"""
01_clean_prepare.py
===================================================================
PURPOSE
    Harmonize the THREE forecast/observation sources into clean,
    analysis-ready tables. Nothing here interprets the data; it only
    cleans, standardizes keys, and reshapes to tidy long/wide form so
    that 02_* and 03_* can run on consistent inputs.

THE THREE SOURCES (all under IECC/)
    1. Rain Forecast 6 month   - province x month forecast rainfall (mm),
                                 issued monthly, 6 months ahead, 2024-2026.
    2. Flood Forecast 6 month  - TAMBON (subdistrict) x month categorical
                                 flood-risk forecast (norisk / flood risk /
                                 flashflood), issued monthly, 6 months ahead.
    3. Flood Historical Data   - actual province x year flood damage,
                                 2019-2025. Already cleaned by the sibling
                                 project (flood_exposure_analysis); we reuse
                                 its province_year.csv as the "actuals".

KEY ALIGNMENT (verified: 77/77 provinces match on every join)
    rain.Province_ID  ==  flood_forecast.PROV_CODE  ==  standard TH prov code
    normalized Thai province name  ==  historical 'province'

OUTPUTS  (written to ./data/)
    rain_province_month.csv       - province x (forecast year,month) consensus
                                    rainfall (mean across issuances) + season/qtr
    flood_forecast_province_month.csv - province x (target year,month) share of
                                    tambons flagged flood / flashflood (most
                                    recent issuance per target month)
    province_meta.csv             - province code, TH name, region (TH+EN)
    historical_province_year.csv  - copy of the cleaned actuals (self-contained)
===================================================================
"""

import os
import re
import glob
import pandas as pd
import numpy as np

# ===================================================================
# SECTION 0 - Paths & constants
# ===================================================================
IECC = "/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC"
RAIN_DIR = os.path.join(IECC, "Rain Forecast 6 month")
FLOOD_FC_DIR = os.path.join(IECC, "Flood Forecast 6 month")

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data")
os.makedirs(OUT, exist_ok=True)

# The sibling project already cleaned the DDPM historical damage records.
# We reuse that artifact as our "actuals" rather than re-parsing 7 raw files.
HIST_SRC = os.path.join(BASE, "..", "flood_exposure_analysis", "data", "province_year.csv")

# Region code -> (Thai, English). From flood-forecast REGION_CODE field.
REGION_MAP = {
    1: ("เหนือ", "North"),
    2: ("ตะวันออกเฉียงเหนือ", "Northeast"),
    3: ("กลาง", "Central"),
    4: ("ตะวันออก", "East"),
    5: ("ใต้", "South"),
}

# Thai meteorological seasons (by calendar month). The monsoon/rainy season
# (Jun-Oct) is the flood-driving window; this mapping powers the seasonal cut.
SEASON_BY_MONTH = {
    1: "Cool/Dry", 2: "Cool/Dry",
    3: "Hot", 4: "Hot", 5: "Hot",
    6: "Rainy/Monsoon", 7: "Rainy/Monsoon", 8: "Rainy/Monsoon",
    9: "Rainy/Monsoon", 10: "Rainy/Monsoon",
    11: "Cool/Dry", 12: "Cool/Dry",
}
QUARTER_BY_MONTH = {m: f"Q{(m - 1) // 3 + 1}" for m in range(1, 13)}


# ===================================================================
# SECTION 1 - Shared cleaning helpers
# ===================================================================
def norm_province(s):
    """Standardize a Thai province name: drop the 'จ.' prefix, collapse
    whitespace, and unify the several spellings of Bangkok so the name
    joins cleanly to the historical actuals."""
    s = (s.astype(str)
           .str.replace(r"\s+", " ", regex=True)
           .str.replace(r"^จ\.", "", regex=True)
           .str.strip())
    fixes = {"กรุงเทพฯ": "กรุงเทพมหานคร", "กทม.": "กรุงเทพมหานคร", "กทม": "กรุงเทพมหานคร"}
    return s.replace(fixes)


def add_calendar_keys(df, month_col="forecast_month"):
    """Attach season and quarter labels from a month column (1-12)."""
    df["season"] = df[month_col].map(SEASON_BY_MONTH)
    df["quarter"] = df[month_col].map(QUARTER_BY_MONTH)
    return df


# ===================================================================
# SECTION 2 - Province metadata (code <-> name <-> region)
#   Built from the latest flood-forecast file, which carries the full
#   geographic hierarchy. This is the canonical province dictionary every
#   other table joins back to.
# ===================================================================
def build_province_meta():
    latest = sorted(glob.glob(os.path.join(FLOOD_FC_DIR, "2*FloodForecast_6month.xlsx")))[-1]
    ff = pd.read_excel(latest, usecols=["PROV_CODE", "PROV_T", "REGION_CODE"])
    meta = (ff.drop_duplicates("PROV_CODE")
              .rename(columns={"PROV_CODE": "province_code", "PROV_T": "province"}))
    meta["province"] = norm_province(meta["province"])
    meta["region_th"] = meta["REGION_CODE"].map(lambda c: REGION_MAP[c][0])
    meta["region_en"] = meta["REGION_CODE"].map(lambda c: REGION_MAP[c][1])
    meta = meta[["province_code", "province", "region_th", "region_en"]].sort_values("province_code")
    return meta.reset_index(drop=True)


# ===================================================================
# SECTION 3 - Rain forecast: harmonize 2024-2026 -> tidy long table
#   Issues fixed here:
#     - rainfall column name differs by year ('Rainfall' vs 'Rainfall.mm.')
#     - province names carry the 'จ.' prefix in 2025/2026 but not 2024
#     - a stray '_id' index column
#   Each file holds multiple monthly issuances; for a given (target year,
#   target month) we average rainfall across issuances to get the
#   *consensus* expected rainfall (smooths single-run noise).
# ===================================================================
def load_rain_forecast(meta):
    frames = []
    for f in sorted(glob.glob(os.path.join(RAIN_DIR, "*rainfall-forecast.csv"))):
        df = pd.read_csv(f)
        # Standardize the rainfall column across the year-to-year schema drift.
        rain_col = "Rainfall.mm." if "Rainfall.mm." in df.columns else "Rainfall"
        df = df.rename(columns={
            rain_col: "rainfall_mm",
            "Initial_Year": "init_year", "Initial_Month": "init_month",
            "Forecast_Year": "forecast_year", "Foreast_Month": "forecast_month",
            "Province_ID": "province_code",
        })
        df = df[["init_year", "init_month", "forecast_year", "forecast_month",
                 "province_code", "rainfall_mm"]]
        df["rainfall_mm"] = pd.to_numeric(df["rainfall_mm"], errors="coerce")
        frames.append(df)

    raw = pd.concat(frames, ignore_index=True)

    # Consensus = mean rainfall across all issuances that targeted the same
    # (province, forecast year, forecast month); n_runs records how many.
    consensus = (raw.groupby(["province_code", "forecast_year", "forecast_month"])
                    .agg(rainfall_mm=("rainfall_mm", "mean"),
                         n_runs=("rainfall_mm", "size"))
                    .reset_index())
    consensus = consensus.merge(meta[["province_code", "province", "region_en"]],
                                on="province_code", how="left")
    consensus = add_calendar_keys(consensus, "forecast_month")
    return consensus.sort_values(["forecast_year", "forecast_month", "province_code"])


# ===================================================================
# SECTION 4 - Flood forecast: TAMBON categorical -> province at-risk share
#   Each monthly file (issued YYYYMM) forecasts the next 6 months at
#   subdistrict level with TYPE_E in {norisk, flood risk, flashflood}.
#   A given target month appears in up to 6 issuances (different lead times);
#   we keep the MOST RECENT issuance for each target month (shortest lead =
#   best information), then collapse tambons to a province-month share:
#       share_atrisk = (flood + flashflood tambons) / tambons in province
#   tracked separately for the two risk TYPES.
# ===================================================================
def load_flood_forecast(meta):
    files = sorted(glob.glob(os.path.join(FLOOD_FC_DIR, "2*FloodForecast_6month.xlsx")))
    use = ["PROV_CODE", "TYPE_E", "YEAR", "MONTH"]
    parts = []
    for f in files:
        # Issuance date is encoded in the filename: 202606FloodForecast_...
        issue = os.path.basename(f)[:6]
        d = pd.read_excel(f, usecols=use)
        d["issue"] = int(issue)            # e.g. 202606, used to pick latest run
        parts.append(d)
    allff = pd.concat(parts, ignore_index=True)

    # For each (province, target year, target month) keep only the latest issuance.
    allff = allff.sort_values("issue")
    latest_issue = (allff.groupby(["PROV_CODE", "YEAR", "MONTH"])["issue"]
                         .transform("max"))
    allff = allff[allff["issue"] == latest_issue]

    # Count tambons by risk type within each province-target-month cell.
    g = (allff.groupby(["PROV_CODE", "YEAR", "MONTH", "TYPE_E"])
              .size().unstack("TYPE_E", fill_value=0).reset_index())
    for c in ["norisk", "flood risk", "flashflood"]:
        if c not in g.columns:
            g[c] = 0
    g["n_tambon"] = g[["norisk", "flood risk", "flashflood"]].sum(axis=1)
    g["share_flood"] = g["flood risk"] / g["n_tambon"]
    g["share_flash"] = g["flashflood"] / g["n_tambon"]
    g["share_atrisk"] = (g["flood risk"] + g["flashflood"]) / g["n_tambon"]

    g = g.rename(columns={"PROV_CODE": "province_code", "YEAR": "forecast_year",
                          "MONTH": "forecast_month",
                          "flood risk": "n_flood", "flashflood": "n_flash"})
    g = g.merge(meta[["province_code", "province", "region_en"]],
                on="province_code", how="left")
    g = add_calendar_keys(g, "forecast_month")
    keep = ["province_code", "province", "region_en", "forecast_year", "forecast_month",
            "season", "quarter", "n_tambon", "n_flood", "n_flash",
            "share_flood", "share_flash", "share_atrisk"]
    return g[keep].sort_values(["forecast_year", "forecast_month", "province_code"])


# ===================================================================
# SECTION 5 - Historical actuals (reuse sibling cleaned output)
# ===================================================================
def load_historical(meta):
    hist = pd.read_csv(HIST_SRC)
    hist["province"] = norm_province(hist["province"])
    hist = hist.merge(meta[["province", "province_code", "region_en"]],
                      on="province", how="left")
    return hist


# ===================================================================
# SECTION 6 - Run & write
# ===================================================================
if __name__ == "__main__":
    meta = build_province_meta()
    meta.to_csv(os.path.join(OUT, "province_meta.csv"), index=False, encoding="utf-8-sig")

    rain = load_rain_forecast(meta)
    rain.to_csv(os.path.join(OUT, "rain_province_month.csv"), index=False, encoding="utf-8-sig")

    flood_fc = load_flood_forecast(meta)
    flood_fc.to_csv(os.path.join(OUT, "flood_forecast_province_month.csv"),
                    index=False, encoding="utf-8-sig")

    hist = load_historical(meta)
    hist.to_csv(os.path.join(OUT, "historical_province_year.csv"),
                index=False, encoding="utf-8-sig")

    # ---- console summary so a run is self-documenting ----
    print("province_meta      :", meta.shape, "| regions:", meta.region_en.unique().tolist())
    print("rain_province_month:", rain.shape,
          "| years:", sorted(rain.forecast_year.unique()),
          "| provinces:", rain.province_code.nunique())
    print("flood_forecast     :", flood_fc.shape,
          "| years:", sorted(flood_fc.forecast_year.unique()),
          "| mean at-risk share:", round(flood_fc.share_atrisk.mean(), 4))
    print("historical actuals :", hist.shape,
          "| years:", sorted(hist.year.unique()))
    print("\nRain consensus by forecast year x season (mean mm/province-month):")
    print(rain.pivot_table(index="forecast_year", columns="season",
                           values="rainfall_mm", aggfunc="mean").round(1).to_string())
    print("\nFlood-forecast at-risk share by year x season (mean):")
    print(flood_fc.pivot_table(index="forecast_year", columns="season",
                               values="share_atrisk", aggfunc="mean").round(4).to_string())

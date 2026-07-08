from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

IECC = Path("/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC")
FORECAST_DIR = IECC / "Flood Forecast 6 month"
GEOJSON = IECC / "TH_TAMBON_json" / "tha_admbnda_adm3_rtsd_20220121_geo.json"
HIST_CSV = IECC / "monthly-flood-risk-area.csv"

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
FIG = HERE / "figures"
OUT.mkdir(exist_ok=True)
(FIG / "forecast_merge").mkdir(parents=True, exist_ok=True)
(FIG / "vs_retro").mkdir(parents=True, exist_ok=True)


ANALYSIS_YEARS = [2023, 2024, 2025]  # 3-yr compare (Mar has only 2: 202303 missing)


TYPE_TO_CLASS = {
    "norisk": "none",
    "flashflood": "flashflood",
    "inundation": "flood",
    "flood risk": "flood",
}
FLASH_RED = "#d62728" 
FLOOD_BLUE = "#1f77b4" 

HIST_RISK_LEVEL = {  
    "เสี่ยงต่ำ": 1,       # 1-3
    "เสี่ยงปานกลาง": 2,   # 4-8
    "เสี่ยงสูง": 3,       # 9-17
}
HIST_LEVEL_EN = {0: "none", 1: "low", 2: "medium", 3: "high"}


def geocode_from_pcode(pcode) -> str:
    return re.sub(r"^TH", "", str(pcode)).strip()


def report_target_months(issue_month: int) -> list[int]:
    return [((issue_month - 1 + k) % 12) + 1 for k in range(6)]

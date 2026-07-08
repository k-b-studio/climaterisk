import os
import re
import pandas as pd
import numpy as np

SRC = "/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC/Flood Historical Data"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)

# Harmonized exposure dimensions (province x year)
DIMS = [
    "events", "districts_affected", "subdistricts_affected", "villages_affected",
    "affected_people", "affected_households", "evacuated_people", "evacuated_households",
    "deaths", "missing", "injured",
    "housing_units", "business_sites", "agriculture_rai", "livestock_head",
    "fisheries_units", "transport_sites", "infrastructure_sites", "total_damage_thb",
]


def num(s):
    """Coerce a series to numeric: strip commas/spaces, '-'/blank -> 0."""
    if s is None:
        return None
    s = s.astype(str).str.replace(",", "", regex=False).str.strip()
    s = s.replace({"-": "0", "": "0", "nan": "0", "None": "0"})
    return pd.to_numeric(s, errors="coerce").fillna(0)


def clean_name(s):
    return (s.astype(str)
             .str.replace("\n", " ", regex=False)
             .str.replace(r"\s+", " ", regex=True)
             .str.strip())


def norm_province(s):
    s = clean_name(s)
    s = s.str.replace(r"^จ\.", "", regex=True).str.strip()
    fixes = {"กรุงเทพฯ": "กรุงเทพมหานคร", "กทม.": "กรุงเทพมหานคร", "กทม": "กรุงเทพมหานคร"}
    return s.replace(fixes)


def find_col(cols, *patterns):
    """Return first column whose cleaned name matches any regex pattern."""
    for p in patterns:
        for c in cols:
            if re.search(p, re.sub(r"\s+", "", str(c))):
                return c
    return None


def sum_cols(df, *patterns):
    """Sum (row-wise) every column matching any of the given regexes."""
    cleaned = {c: re.sub(r"\s+", "", str(c)) for c in df.columns}
    hits = [c for c, cc in cleaned.items() if any(re.search(p, cc) for p in patterns)]
    if not hits:
        return pd.Series(0, index=df.index, dtype=float)
    return sum(num(df[c]) for c in hits)


def read_with_header_row(path, sheet, header_value="จังหวัด", search_col=0, max_scan=6):
    """Read a sheet whose real header row contains `header_value` (multi-row headers)."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    hdr = None
    for i in range(max_scan):
        if str(raw.iloc[i, search_col]).strip() == header_value or \
           header_value in [str(v).strip() for v in raw.iloc[i].tolist()]:
            hdr = i
            break
    if hdr is None:
        raise ValueError(f"header row not found in {path}:{sheet}")
    df = raw.iloc[hdr + 1:].copy()
    df.columns = clean_name(pd.Series(raw.iloc[hdr])).tolist()
    return df.reset_index(drop=True)


def drop_total_rows(df, prov_col):
    p = df[prov_col].astype(str)
    mask = (~p.str.contains("รวม", na=False)) & (p.str.strip() != "") & \
           (p.str.strip().str.lower() != "nan") & (~p.str.strip().str.fullmatch(r"[\d\.,]+"))
    return df[mask].copy()


records_p, records_d = [], []   # province-year rows / district-year rows


def add_province_rows(g, year, mapping):
    """g: groupby(province) aggregated DataFrame indexed by province."""
    for prov, row in g.iterrows():
        rec = {"year": year, "province": prov}
        rec.update({k: row.get(k, np.nan) for k in DIMS})
        records_p.append(rec)


# ----------------------------------------------------------------------------
# BE 2562 (2019) — already province-level aggregate, one row per province
# ----------------------------------------------------------------------------
def load_2562():
    f = os.path.join(SRC, "gd027_flood_stat2562_final.xlsx")
    df = pd.read_excel(f, sheet_name="flood2562cut")
    df = df.iloc[1:]                                   # row 0 = Thai labels
    df = drop_total_rows(df, "Province")
    df["province"] = norm_province(df["Province"])

    out = pd.DataFrame({"province": df["province"]})
    out["events"] = np.nan                              # not reported in 2562 file
    out["districts_affected"] = num(df["District"])     # district COUNT in this file
    out["subdistricts_affected"] = num(df["Subdistrict Count"])
    out["villages_affected"] = num(df["Village Count"])
    out["affected_people"] = sum_cols(df, r"^Population$")
    out["affected_households"] = sum_cols(df, r"^households$")
    out["evacuated_people"] = sum_cols(df, r"^EvacuatedPeople$")
    out["evacuated_households"] = sum_cols(df, r"^EvacuatedHouseholds$")
    out["deaths"] = sum_cols(df, r"^Deaths$")
    out["missing"] = sum_cols(df, r"^Missing$")
    out["injured"] = sum_cols(df, r"^Injured$")
    out["housing_units"] = sum_cols(df, r"^Homes$", r"^partial_home$")
    out["business_sites"] = sum_cols(df, r"^Hotels$")
    out["agriculture_rai"] = sum_cols(df, r"^RiceFields$", r"^GardenCrops$", r"^FieldCrops$")
    out["livestock_head"] = sum_cols(df, r"^Cattle$", r"^Buffaloes$", r"^Goats$", r"^Chickens$", r"^Ducks$")
    out["fisheries_units"] = sum_cols(df, r"^FishPonds$", r"^PrawnPonds$", r"^FishCages$")
    out["transport_sites"] = sum_cols(df, r"^Roads$", r"^Bridges$")
    out["infrastructure_sites"] = sum_cols(
        df, r"^Dams$", r"^Weirs$", r"^Mines$", r"^Levees$", r"^WaterSources$", r"^Drains$",
        r"^Electricity$", r"^WaterSupply$", r"^Temples/Mosques$", r"^Schools$",
        r"^Hospitals$", r"^government_offices$")
    out["total_damage_thb"] = sum_cols(df, r"^TotalDamage\(THB\)$")
    g = out.groupby("province").sum(min_count=1)
    g["events"] = np.nan
    add_province_rows(g, 2019, None)


# ----------------------------------------------------------------------------
# BE 2563-2565 (2020-2022) — district x event level, Thai columns
# ----------------------------------------------------------------------------
def load_event_level_thai(fname, sheet, year, dynamic_header):
    f = os.path.join(SRC, fname)
    if dynamic_header:
        df = read_with_header_row(f, sheet)
    else:
        df = pd.read_excel(f, sheet_name=sheet)
        df.columns = clean_name(pd.Series(df.columns)).tolist()
    df = drop_total_rows(df, "จังหวัด")
    # 2565 sheet mixes district rows with per-province total rows whose อำเภอ
    # holds the numeric district count — these duplicate the detail, drop them
    df = df[~clean_name(df["อำเภอ"]).str.fullmatch(r"[\d\.,]+")]
    df["province"] = norm_province(df["จังหวัด"])
    df["district"] = clean_name(df["อำเภอ"])

    d = pd.DataFrame({"province": df["province"], "district": df["district"]})
    d["subdistricts"] = sum_cols(df, r"^ตำบล/เทศบาล$", r"^ตำบล/อปท\.$") \
        if find_col(df.columns, r"^ตำบล/เทศบาล$", r"^ตำบล/อปท\.$") is not None \
        else sum_cols(df, r"^จำนวนตำบลและอปท") if find_col(df.columns, r"^จำนวนตำบลและอปท") is not None \
        else sum_cols(df, r"^จำนวนตำบล$")
    d["villages"] = sum_cols(df, r"^หมู่บ้าน/ชุมชน$") \
        if find_col(df.columns, r"^หมู่บ้าน/ชุมชน$") is not None \
        else sum_cols(df, r"^จำนวนหมู่บ้านและชุมชน$") if find_col(df.columns, r"^จำนวนหมู่บ้านและชุมชน$") is not None \
        else sum_cols(df, r"^จำนวนหมู่บ้าน$", r"^จำนวนหมู่ที่$")
    d["affected_people"] = sum_cols(df, r"^ราษฎร\(คน\)$")
    d["affected_households"] = sum_cols(df, r"^ราษฎร\(ครัวเรือน\)$")
    d["evacuated_people"] = sum_cols(df, r"^อพยพ\(คน\)$")
    d["evacuated_households"] = sum_cols(df, r"^อพยพ\(ครัวเรือน\)$")
    d["deaths"] = sum_cols(df, r"^เสียชีวิต\(คน\)$")
    d["missing"] = sum_cols(df, r"^สูญหาย\(คน\)$")
    d["injured"] = sum_cols(df, r"^บาดเจ็บ\(คน\)$")
    d["housing_units"] = sum_cols(df, r"^บ้านพักอาศัย\(หลัง\)$", r"^บ้านเรือนบางส่วน\(หลัง\)$",
                                  r"^อาคารชุด\(คอนโด\)$", r"^อาคารพาณิชย์\(หลัง\)$")
    d["business_sites"] = sum_cols(df, r"^โรงงาน\(แห่ง\)$", r"^บริษัท$", r"^บริษัท\(แห่ง\)$", r"^โรงแรม\(แห่ง\)$")
    d["agriculture_rai"] = sum_cols(df, r"^นาข้าว\(ไร่\)$", r"^พืชสวน\(ไร่\)$", r"^พืชไร่\(ไร่\)$",
                                    r"^พืชต้นทุนสูง\(ไร่\)$", r"^พืชต้นทุนสูง$",
                                    r"^\*พืชต้นทุนสูง\(ไร่\)\(เฉลี่ย1ไร่มี20ต้น\)$")
    d["livestock_head"] = sum_cols(df, r"^โค\(ตัว\)$", r"^กระบือ\(ตัว\)$", r"^แพะ\(ตัว\)$",
                                   r"^แกะ\(ตัว\)$", r"^ไก่\(ตัว\)$", r"^เป็ด\(ตัว\)$")
    d["fisheries_units"] = sum_cols(df, r"^บ่อปลา\(บ่อ\)$", r"^บ่อกุ้ง\(บ่อ\)$", r"^กระชังปลา\(แห่ง\)$")
    d["transport_sites"] = sum_cols(df, r"^ถนน\(สาย\)$", r"^สะพาน/คอฯ\(แห่ง\)$")
    d["infrastructure_sites"] = sum_cols(df, r"^ทำนบ\(แห่ง\)$", r"^ฝาย\(แห่ง\)$", r"^เหมือง\(แห่ง\)$",
                                         r"^วัด/มัสยิด\(แห่ง\)$", r"^โรงเรียน\(แห่ง\)$", r"^โรงพยาบาล\(แห่ง\)$",
                                         r"^สถานที่ราชการ\(แห่ง\)$", r"^พนังกั้นน้ำ/คันคลอง\(แห่ง\)$",
                                         r"^บ่อน้ำ/อ่างเก็บน้ำ\(แห่ง\)$", r"^ท่อระบายน้ำ\(แห่ง\)$",
                                         r"^ไฟฟ้า\(แห่ง\)$", r"^ประปา\(แห่ง\)$")

    # district-level rows
    gd = d.groupby(["province", "district"]).agg(
        events=("affected_people", "size"),
        affected_people=("affected_people", "sum"),
        affected_households=("affected_households", "sum"),
        housing_units=("housing_units", "sum"),
        agriculture_rai=("agriculture_rai", "sum"),
        deaths=("deaths", "sum"),
    ).reset_index()
    gd["year"] = year
    records_d.extend(gd.to_dict("records"))

    # province-level rows
    g = d.groupby("province").agg(
        events=("affected_people", "size"),
        districts_affected=("district", "nunique"),
        subdistricts_affected=("subdistricts", "sum"),
        villages_affected=("villages", "sum"),
        **{k: (k, "sum") for k in [
            "affected_people", "affected_households", "evacuated_people", "evacuated_households",
            "deaths", "missing", "injured", "housing_units", "business_sites", "agriculture_rai",
            "livestock_head", "fisheries_units", "transport_sites", "infrastructure_sites"]},
    )
    g["total_damage_thb"] = np.nan
    add_province_rows(g, year, None)


# ----------------------------------------------------------------------------
# BE 2566-2567 (2023-2024) — village-level records
# ----------------------------------------------------------------------------
def load_village_level(fname, sheet, year, thai_header):
    f = os.path.join(SRC, fname)
    if thai_header:   # 2566: real header is the row containing 'จังหวัด'
        df = read_with_header_row(f, sheet)
        prov_c, dist_c, subd_c, vill_c = "จังหวัด", "อำเภอ/เขต", "รหัสตำบล", "รหัสหมู่บ้าน"
        cmap = {
            "affected_people": r"^ผู้ได้รับผลกระทบ\(คน\)$",
            "affected_households": r"^ผู้ได้รับผลกระทบ\(ครัวเรือน\)$",
            "evacuated_people": r"^ผู้อพยพ\(คน\)$",
            "evacuated_households": r"^ผู้อพยพ\(ครัวเรือน\)$",
            "deaths": r"^ผู้เสียชีวิต\(คน\)$", "missing": r"^สูญหาย\(คน\)$", "injured": r"^ผู้บาดเจ็บ\(คน\)$",
            "housing_units": r"^ด้านที่อยู่อาศัย", "business_sites": r"^ด้านธุรกิจ",
            "agriculture_rai": r"^ด้านการเกษตร", "livestock_head": r"^ด้านปศุสัตว์",
            "fisheries_units": r"^ด้านประมง", "transport_sites": r"^ด้านคมนาคม",
        }
        infra_pats = [r"^ด้านสาธารณสุข", r"^ด้านศาสนาวัฒนธรรม", r"^ด้านสถานศึกษา",
                      r"^ด้านสาธารณูปโภค", r"^ด้านสถานที่ราชการ", r"^ด้านสาธารณประโยชน์อื่น",
                      r"^ด้านทรัพย์สินราชการ"]
    else:             # 2567: English header in row 0, Thai labels in first data row
        df = pd.read_excel(f, sheet_name=sheet)
        df.columns = clean_name(pd.Series(df.columns)).tolist()
        df = df.iloc[1:]
        prov_c, dist_c, subd_c, vill_c = "Province", "District", "Sub-district Code", "Village Code"
        cmap = {
            "affected_people": r"^AffectedPeople$", "affected_households": r"^AffectedHouseholds$",
            "evacuated_people": r"^Evacuees$", "evacuated_households": r"^Evacuees\(Households\)$",
            "deaths": r"^fatalities_count$", "missing": r"^MissingPersons$", "injured": r"^injuries_count$",
            "housing_units": r"^Housing\(Units\)$", "business_sites": r"^Business\(Sites\)$",
            "agriculture_rai": r"^Agriculture\(Acres\)$", "livestock_head": r"^Livestock\(Head\)$",
            "fisheries_units": r"^Fisheries\(Ponds\)$", "transport_sites": r"^Transportation\(Sites\)$",
        }
        infra_pats = [r"^Health\(Sites\)$", r"^Religion/Culture\(Sites\)$", r"^Education/Sports\(Sites\)$",
                      r"^Utilities\(Sites\)$", r"^GovernmentSites$", r"^OtherPublicBenefit\(Sites\)$",
                      r"^Gov\./PrivateProperty\(Units\)$"]

    df = drop_total_rows(df, prov_c)
    df = df[clean_name(df[prov_c]) != ""]
    df = df[~clean_name(df[dist_c]).str.fullmatch(r"[\d\.,]+")]   # stray total rows
    d = pd.DataFrame({"province": norm_province(df[prov_c]), "district": clean_name(df[dist_c])})
    d["subd_key"] = df[subd_c].astype(str)
    d["vill_key"] = df[vill_c].astype(str) + "|" + d["district"]
    for k, pat in cmap.items():
        d[k] = sum_cols(df, pat)
    d["infrastructure_sites"] = sum_cols(df, *infra_pats)

    gd = d.groupby(["province", "district"]).agg(
        events=("affected_people", "size"),
        affected_people=("affected_people", "sum"),
        affected_households=("affected_households", "sum"),
        housing_units=("housing_units", "sum"),
        agriculture_rai=("agriculture_rai", "sum"),
        deaths=("deaths", "sum"),
    ).reset_index()
    gd["year"] = year
    records_d.extend(gd.to_dict("records"))

    g = d.groupby("province").agg(
        events=("affected_people", "size"),
        districts_affected=("district", "nunique"),
        subdistricts_affected=("subd_key", "nunique"),
        villages_affected=("vill_key", "nunique"),
        **{k: (k, "sum") for k in cmap if k not in ("affected_people",)},
        affected_people=("affected_people", "sum"),
        infrastructure_sites=("infrastructure_sites", "sum"),
    )
    g["total_damage_thb"] = np.nan
    add_province_rows(g, year, None)


# ----------------------------------------------------------------------------
# BE 2568 (2025) — province-level aggregate with region subtotals
# ----------------------------------------------------------------------------
def load_2568():
    f = os.path.join(SRC, "gd027_flood_stat2568_final.xlsx")
    df = pd.read_excel(f, sheet_name="อุทกภัย68")
    df.columns = clean_name(pd.Series(df.columns)).tolist()
    df = df.iloc[1:]                                    # Thai label row
    df = df[~df["region"].astype(str).str.contains("ผลรวม", na=False)]
    df = drop_total_rows(df, "Province")
    df["province"] = norm_province(df["Province"])

    out = pd.DataFrame({"province": df["province"]})
    out["events"] = num(df["Time"])
    out["districts_affected"] = num(df["District"])
    out["subdistricts_affected"] = num(df["Sub-district"])
    out["villages_affected"] = num(df["Community"])
    out["affected_people"] = sum_cols(df, r"^AffectedPeople$")
    out["affected_households"] = sum_cols(df, r"^AffectedHouseholds$")
    out["evacuated_people"] = sum_cols(df, r"^Evacuees$")
    out["evacuated_households"] = sum_cols(df, r"^Evacuees\(Households\)$")
    out["deaths"] = sum_cols(df, r"^fatalities_count$")
    out["missing"] = sum_cols(df, r"^MissingPersons$")
    out["injured"] = sum_cols(df, r"^injuries_count$")
    out["housing_units"] = sum_cols(df, r"^Housing\(Units\)$")
    out["business_sites"] = sum_cols(df, r"^Business\(Sites\)$")
    out["agriculture_rai"] = sum_cols(df, r"^Agriculture\(Acres\)$")
    out["livestock_head"] = sum_cols(df, r"^Livestock\(Head\)$")
    out["fisheries_units"] = sum_cols(df, r"^Fisheries\(Ponds\)$")
    out["transport_sites"] = sum_cols(df, r"^Transportation\(Sites\)$")
    out["infrastructure_sites"] = sum_cols(df, r"^Health\(Sites\)$", r"^Religion/Culture\(Sites\)$",
                                           r"^Education/Sports\(Sites\)$", r"^Utilities\(Sites\)$",
                                           r"^GovernmentSites$", r"^OtherPublicBenefit\(Sites\)$",
                                           r"^Gov\./PrivateProperty\(Units\)$")
    out["total_damage_thb"] = np.nan
    g = out.groupby("province").sum(min_count=1)
    add_province_rows(g, 2025, None)


if __name__ == "__main__":
    load_2562()
    load_event_level_thai("gd027_flood_stat2563_final.xlsx", "ความเสียหายรวม", 2020, dynamic_header=False)
    load_event_level_thai("gd027_flood_stat2564_final.xlsx", "ความเสียหายรวม", 2021, dynamic_header=True)
    load_event_level_thai("gd027_flood_stat2565_final.xlsx", "อำเภอ+ทั้งหมด", 2022, dynamic_header=True)
    load_village_level("gd027_flood_stat2566_final.xlsx", "พื้นที่เกิด", 2023, thai_header=True)
    load_village_level("gd027_flood_stat2567_final.xlsx", "อุทกภัย67-รายการพื้นที่เกิด (2)", 2024, thai_header=False)
    load_2568()

    pv = pd.DataFrame(records_p)
    pv = pv[["year", "province"] + DIMS].sort_values(["year", "province"])
    pv.to_csv(os.path.join(OUT, "province_year.csv"), index=False, encoding="utf-8-sig")

    dv = pd.DataFrame(records_d)
    dv = dv[["year", "province", "district", "events", "affected_people", "affected_households",
             "housing_units", "agriculture_rai", "deaths"]].sort_values(["year", "province", "district"])
    dv.to_csv(os.path.join(OUT, "district_year.csv"), index=False, encoding="utf-8-sig")

    print("province_year:", pv.shape, "| years:", sorted(pv.year.unique()),
          "| provinces:", pv.province.nunique())
    print(pv.groupby("year")[["affected_people", "affected_households", "housing_units",
                              "agriculture_rai", "deaths"]].sum().round(0).to_string())
    print("district_year:", dv.shape)


# -*- coding: utf-8 -*-
"""
Each source file has a different schema; this script harmonizes all years into:
  - data/province_year.csv  : one row per province x year, common exposure dimensions
  - data/district_year.csv  : one row per district x year (years with district detail)

Cleaning performed:
  - drop Thai-label sub-header rows, "รวม" subtotal rows, grand-total rows
  - dynamic header detection for multi-row-header sheets (2564/2565/2566)
  - strip whitespace / newlines in names, normalize province names
  - numeric coercion (commas, blanks, '-' -> 0/NaN)
  - Buddhist year -> Gregorian year
"""
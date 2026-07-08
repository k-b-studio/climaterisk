import os
import re
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------- paths
BASE = Path("/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/IECC")
BAY  = Path("/Users/kbstudio/Library/CloudStorage/OneDrive-Personal/Project/BAY")

SRC = {
    "metadata":   (BASE / "Flood Forecast 6 month" / "metadata.xlsx", None,           "GEOCODE"),
    "LATLONG":    (BASE / "LATLONG.xlsx",                            "TAMBON",        "TA_ID"),
    "CodeTAMBON": (BASE / "CodeTAMBON.xlsx",                         "Shape - Copy",  "TAMBON_IDN"),
}


def norm_geocode(s):
    """Normalise a key value to a clean 6-digit string, or NA."""
    if pd.isna(s):
        return pd.NA
    s = str(s).strip()
    if s.endswith(".0"):          # floats read from excel e.g. 910106.0
        s = s[:-2]
    s = re.sub(r"\D", "", s)      # keep digits only
    if s == "":
        return pd.NA
    # Thai tambon code is 6 digits; left-pad shorter, keep as-is otherwise
    return s.zfill(6) if len(s) < 6 else s


# ---------------------------------------------------------------- load
frames = {}
keycols = {}
for name, (path, sheet, key) in SRC.items():
    try:
        df = pd.read_excel(path, sheet_name=sheet) if sheet else pd.read_excel(path)
    except (TimeoutError, OSError) as e:
        raise SystemExit(
            f"[{name}] could not read '{path}': {e}\n"
            f"  This file is likely an OneDrive cloud-only placeholder.\n"
            f"  Make sure the OneDrive app is running, then in Finder right-click\n"
            f"  the file and choose 'Always keep on this device' to download it."
        )
    if key not in df.columns:
        raise SystemExit(
            f"[{name}] expected key column '{key}' not found.\n"
            f"  available columns: {list(df.columns)}"
        )
    df = df.copy()
    df["GEOCODE"] = df[key].map(norm_geocode)
    keycols[name] = key
    frames[name] = df
    dup = df["GEOCODE"].duplicated().sum()
    print(f"[{name:10}] rows={len(df):>6}  unique GEOCODE={df['GEOCODE'].nunique():>6}  "
          f"dup GEOCODE={dup:>4}  null key={df['GEOCODE'].isna().sum():>4}")

# prefix non-key columns so we can tell sources apart after the join
def prep(name):
    df = frames[name].copy()
    # drop duplicate geocodes (keep first) so the join stays 1:1 per source
    df = df.drop_duplicates(subset="GEOCODE")
    ren = {c: f"{name}__{c}" for c in df.columns if c != "GEOCODE"}
    df = df.rename(columns=ren)
    # explicit presence marker so we can tell which sources contributed a row,
    # robust even when a source's key column is itself named "GEOCODE".
    df[f"_present__{name}"] = True
    return df

m  = prep("metadata")
ll = prep("LATLONG")
ct = prep("CodeTAMBON")

# ---------------------------------------------------------------- join (outer)
j = m.merge(ll, on="GEOCODE", how="outer", indicator=False)
j = j.merge(ct, on="GEOCODE", how="outer", indicator=False)

# presence flags per source (based on the explicit per-source marker column)
for name in SRC:
    j[f"in_{name}"] = j[f"_present__{name}"].notna()
j = j.drop(columns=[f"_present__{name}" for name in SRC])
j["n_sources"]     = j[["in_metadata", "in_LATLONG", "in_CodeTAMBON"]].sum(axis=1)
j["match_status"]  = j["n_sources"].map({3: "all_3", 2: "2_of_3", 1: "only_1"})

total = len(j)
print(f"\nJoined rows (union of all GEOCODEs): {total}")
print(j["match_status"].value_counts().to_string())

# ---------------------------------------------------------------- presence summary
presence = (
    j.groupby(["in_metadata", "in_LATLONG", "in_CodeTAMBON"])
     .size().rename("rows").reset_index()
     .sort_values("rows", ascending=False)
)
presence["pct"] = (presence["rows"] / total * 100).round(2)
print("\nPresence breakdown:")
print(presence.to_string(index=False))

# % of each source's geocodes that are missing from the union-join's *full* set
src_summary = []
for name in SRC:
    flag = f"in_{name}"
    present = j[flag].sum()
    missing = total - present
    src_summary.append({
        "source": name,
        "key_column": keycols[name],
        "rows_in_source": int(present),
        "missing_vs_union": int(missing),
        "pct_missing_vs_union": round(missing / total * 100, 2),
    })
src_summary = pd.DataFrame(src_summary)
print("\nPer-source coverage vs union:")
print(src_summary.to_string(index=False))

# ---------------------------------------------------------------- column-level % missing
col_missing = (
    j.isna().mean().mul(100).round(2)
     .rename("pct_missing").reset_index().rename(columns={"index": "column"})
)

# ---------------------------------------------------------------- consistency checks
# Compare attributes that exist in more than one source for the same GEOCODE.
# Pairs of (label, colA, colB) to compare on the rows where both are present.
check_pairs = [
    ("tambon_EN",   "LATLONG__TAMBON_E",   "CodeTAMBON__TAMBON_EN"),
    ("tambon_TH",   "LATLONG__TAMBON_T",   "CodeTAMBON__TAMBON_TN"),
    ("amphoe_EN",   "LATLONG__AMPHOE_E",   "CodeTAMBON__AMPHOE_EN"),
    ("province_EN", "LATLONG__CHANGWAT_E", "CodeTAMBON__PROVINCE_EN"),
    ("lat",         "LATLONG__LAT",        "CodeTAMBON__LATITUDE_CENTER_TAMBON"),
    ("long",        "LATLONG__LONG",       "CodeTAMBON__LONGITUDE_CENTER_TAMBON"),
]

def clean_txt(x):
    if pd.isna(x):
        return pd.NA
    s = str(x).strip().lower()
    s = re.sub(r"^(ต\.|อ\.|จ\.)\s*", "", s)   # strip Thai prefixes ต./อ./จ.
    s = re.sub(r"\s+", " ", s)
    return s

consistency_rows = []
mismatch_frames = []
for label, ca, cb in check_pairs:
    if ca not in j.columns or cb not in j.columns:
        continue
    both = j[j[ca].notna() & j[cb].notna()]
    n = len(both)
    if n == 0:
        continue
    if label in ("lat", "long"):
        a = pd.to_numeric(both[ca], errors="coerce")
        b = pd.to_numeric(both[cb], errors="coerce")
        same = (a.sub(b).abs() <= 0.05)   # within ~5km tolerance for centroid
    else:
        same = both[ca].map(clean_txt).eq(both[cb].map(clean_txt))
    n_same = int(same.sum())
    consistency_rows.append({
        "attribute": label,
        "col_LATLONG": ca,
        "col_CodeTAMBON": cb,
        "compared_rows": n,
        "match": n_same,
        "mismatch": n - n_same,
        "pct_match": round(n_same / n * 100, 2),
    })
    mm = both.loc[~same, ["GEOCODE", ca, cb]].copy()
    if len(mm):
        mm.insert(0, "attribute", label)
        mm.columns = ["attribute", "GEOCODE", "value_LATLONG", "value_CodeTAMBON"]
        mismatch_frames.append(mm)

consistency = pd.DataFrame(consistency_rows)
mismatches  = pd.concat(mismatch_frames, ignore_index=True) if mismatch_frames else \
              pd.DataFrame(columns=["attribute", "GEOCODE", "value_LATLONG", "value_CodeTAMBON"])
print("\nConsistency (rows where both sources have the attribute):")
print(consistency.to_string(index=False) if len(consistency) else "  (no comparable pairs)")

# ---------------------------------------------------------------- missing rows
missing_any = j[j["n_sources"] < 3].copy()
miss_meta   = j[~j["in_metadata"]].copy()
miss_ll     = j[~j["in_LATLONG"]].copy()
miss_ct     = j[~j["in_CodeTAMBON"]].copy()

# ---------------------------------------------------------------- write excel
out_join = os.path.join(BAY, "TAMBON_joined.xlsx")
with pd.ExcelWriter(out_join, engine="openpyxl") as w:
    j.to_excel(w, sheet_name="joined", index=False)
    presence.to_excel(w, sheet_name="presence_summary", index=False)
    src_summary.to_excel(w, sheet_name="source_coverage", index=False)
    col_missing.to_excel(w, sheet_name="pct_missing_by_column", index=False)
    consistency.to_excel(w, sheet_name="consistency_check", index=False)
    mismatches.to_excel(w, sheet_name="consistency_mismatches", index=False)

out_miss = os.path.join(BAY, "TAMBON_missing_rows.xlsx")
with pd.ExcelWriter(out_miss, engine="openpyxl") as w:
    missing_any.to_excel(w, sheet_name="missing_in_any", index=False)
    miss_meta.to_excel(w, sheet_name="missing_in_metadata", index=False)
    miss_ll.to_excel(w, sheet_name="missing_in_LATLONG", index=False)
    miss_ct.to_excel(w, sheet_name="missing_in_CodeTAMBON", index=False)

print(f"\nWrote:\n  {out_join}\n  {out_miss}")
print(f"Missing in >=1 source: {len(missing_any)} rows "
      f"({round(len(missing_any)/total*100,2)}% of union)")

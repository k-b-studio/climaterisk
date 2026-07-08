from __future__ import annotations
import re
import pandas as pd
import config as C

KEEP = ["GEOCODE", "TYPE_E", "YEAR", "MONTH"]


def _read_forecast(f):
    # some months arrive as CSV instead of XLSX (e.g. 202303), Thai-encoded (cp874),
    # and without a GEOCODE column (only TAMBON_IDN).
    if f.suffix.lower() == ".csv":
        return pd.read_csv(f, encoding="cp874")
    return pd.read_excel(f)


def load_long() -> pd.DataFrame:
    files = sorted(p for p in C.FORECAST_DIR.glob("*FloodForecast_6month.*")
                   if p.suffix.lower() in (".xlsx", ".csv"))
    if not files:
        raise FileNotFoundError(f"No forecast files under {C.FORECAST_DIR}")

    seen_types: set[str] = set()
    frames = []
    for f in files:
        issue = re.match(r"(\d{6})", f.name).group(1)            # '202401'
        raw = _read_forecast(f)
        if "GEOCODE" not in raw.columns:
            raw["GEOCODE"] = raw["TAMBON_IDN"]
        df = raw[KEEP].copy()

        esc = r"_x[0-9A-Fa-f]{4}_"
        df["GEOCODE"] = df["GEOCODE"].astype(str).str.replace(esc, "", regex=True).str.strip()
        df["TYPE_E"] = (df["TYPE_E"].astype(str)
                        .str.replace(esc, "", regex=True).str.strip().str.lower())
        seen_types |= set(df["TYPE_E"].unique())
        df["ISSUE"] = issue
        df["ISSUE_YEAR"] = int(issue[:4])
        df["ISSUE_MONTH"] = int(issue[4:])
        frames.append(df)
        print(f"  loaded {f.name:40s} rows={len(df):>7,}")

    unknown = seen_types - set(C.TYPE_TO_CLASS)
    if unknown:
        raise ValueError(f"Unexpected TYPE_E values: {unknown}")

    long = pd.concat(frames, ignore_index=True)
    long["CLASS"] = long["TYPE_E"].map(C.TYPE_TO_CLASS)
    print(f"  -> {len(long):,} rows from {len(files)} files; "
          f"TYPE_E seen = {sorted(seen_types)}")
    return long


def collapse_by_issue(long: pd.DataFrame) -> pd.DataFrame:
    g = long.groupby(["ISSUE", "ISSUE_YEAR", "ISSUE_MONTH", "GEOCODE"])
    out = pd.DataFrame({
        "IS_FLASH": g["CLASS"].apply(lambda s: (s == "flashflood").any()),
        "IS_FLOOD": g["CLASS"].apply(lambda s: (s == "flood").any()),

        "N_FLASH_MONTHS": g["CLASS"].apply(lambda s: (s == "flashflood").sum()),
        "N_FLOOD_MONTHS": g["CLASS"].apply(lambda s: (s == "flood").sum()),
    }).reset_index()
    out["AT_RISK"] = out["IS_FLASH"] | out["IS_FLOOD"]
    return out


def main():
    print("1) Loading forecast files ...")
    long = load_long()
    print("2) Collapsing to one row per (report, Tambon) ...")
    by_issue = collapse_by_issue(long)

    long.to_pickle(C.OUT / "forecast_long.pkl")
    by_issue.to_pickle(C.OUT / "forecast_by_issue.pkl")

    print("\n================= PANEL SUMMARY =================")
    print(f"Reports (ISSUE) ............ {long['ISSUE'].nunique()} "
          f"({long['ISSUE'].min()}..{long['ISSUE'].max()})")
    print(f"Tambons (GEOCODE) .......... {long['GEOCODE'].nunique():,}")
    print("Reports per ISSUE_MONTH (years available):")
    rpm = (by_issue.groupby("ISSUE_MONTH")["ISSUE_YEAR"]
           .apply(lambda s: sorted(s.unique())))
    for m, yrs in rpm.items():
        print(f"   month {m:>2}: {yrs}")
    print("\nAt-risk Tambons per report (flash / flood / any):")
    agg = by_issue.groupby("ISSUE").agg(
        flash=("IS_FLASH", "sum"), flood=("IS_FLOOD", "sum"),
        any=("AT_RISK", "sum"))
    print(agg.to_string())


if __name__ == "__main__":
    main()

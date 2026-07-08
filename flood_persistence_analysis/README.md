# Flood-Forecast Persistence & Historical Validation (Tambon scale)

Two questions, both answered at **Tambon (ADM3, 6-digit GEOCODE)** resolution.

1. **Task 1 — Same-month report, different years.** For a report issued in a
   given calendar month, how much does its at-risk footprint *repeat* from year
   to year? Areas flagged **every** year are the stable core (**hard/dark
   colour**); areas flagged in only **one** year are new/volatile (**light
   colour**). Flash flood is drawn in **red**, flood/inundation in **blue**.
2. **Task 2 — Validate against history.** Does the forecast footprint match the
   **17-year monthly flood climatology** (`monthly-flood-risk-area.csv`)?

## Data

| Source | What | Key |
|---|---|---|
| `Flood Forecast 6 month/*` | 42 monthly reports, **202301–202606** (41 `.xlsx` + 202303 as `.csv`). Each is issued in month `YYYYMM` and forecasts the **next 6 calendar months**. `TYPE_E ∈ {norisk, flashflood, inundation, flood risk}`. | `GEOCODE` |
| `TH_TAMBON_json/...adm3...geo.json` | 7,425 Tambon polygons. `ADM3_PCODE = 'TH' + GEOCODE`. | `ADM3_PCODE → GEOCODE` |
| `monthly-flood-risk-area.csv` | Historical flood occurrences per `(Month, GEOCODE)` over 17 yr, with `COUNT 17 YEAR` and `RISK` (low/medium/high). | `GEOCODE` |

**Coding.** `inundation` and `flood risk` are the same code-2 *flood* class
(the label changed after 202405). `flashflood` = red, `flood` = blue.
A Tambon is "flagged" by a report if that class appears in **any** of the
report's 6 horizon months.

**Join quality (validator notes).**
- Forecast↔map: 7,381 / 7,387 forecast Tambons matched. The 6 unmatched
  (`201201, 401050, 530407, 630191, 810150, 860805`) are post-2022 Tambon
  splits absent from the 2022 boundary file — negligible.
- CSV↔map: 6,433 / 6,435 matched. CSV ⊆ forecast (every historical Tambon
  exists in the forecast universe).
- All GEOCODEs are 6 digits in every source. Loader handles two 2023 quirks:
  the 202303 report is a Thai-encoded **CSV** (read as `cp874`) with only
  `TAMBON_IDN` (→ `GEOCODE`), and some cells carry openpyxl control-char escapes
  (e.g. `norisk_x000D_`); both are normalised on load.

## Pipeline

```
01_build_panel.py        -> output/forecast_long.pkl, forecast_by_issue.pkl
02_persistence_maps.py   -> output/_persistence.csv ; figures/forecast_merge/*  (TASK 1)
03_validate_vs_history.py-> output/_*.csv ; figures/vs_retro/*                  (TASK 2)
```
Run in order. `config.py` holds paths + shared coding. (`.pkl` caches the slow
Excel read; pyarrow not required.)

## Task 1 — results

**Analysis years: 2023, 2024 & 2025** (`ANALYSIS_YEARS` in `config.py`). 2026 is
excluded (only months 01–06). **Every month compares exactly 3 years** (202303
arrives as a CSV — see data notes). The colour ramp adapts to the year count, so
maps show **3 levels**: light = new / 1 yr, mid = 2 yrs, dark = always / 3 yrs.
"always" = flagged in all 3 years.
Per `(issue-month, type)` map: `figures/forecast_merge/<flash|flood>_monthMM.png`;
overviews `_contact_<flash|flood>.png`; per-Tambon table
`output/_persistence.csv`.

**Forecasts are seasonally stable, and the stability is itself seasonal.**
Share of flagged Tambons that recur in **all 3 years** (3/3 = "always"):

| Season | Flash "always" | Flood "always" |
|---|---|---|
| Dry (Jan–Feb) | 13–23 % | 3 % |
| Pre-monsoon (Mar–Apr) | 46–52 % | 11–31 % |
| Monsoon (May–Oct) | 23–49 % | 36–44 % |
| Late (Nov–Dec) | 14–30 % | 11–43 % |

The 3/3 bar is stricter than the earlier 2/2, so "always" shares run lower than
the 2-year run; the seasonal pattern (big repeatable monsoon core, sporadic dry
season) is unchanged.

- Monsoon reports rest on a **large, repeatable core** — the same hotspots are
  named year after year. Dry-season reports are mostly one-off (>60 % of flood
  flags appear in a single year) because off-season flooding is sporadic.
- **Geography separates cleanly:** flash-flood "always" cells sit in the
  mountainous **North** and the steep **southern peninsula**; flood/inundation
  "always" cells fill the flat **Chao Phraya basin**, the **Northeast**, and the
  lower peninsula. Physically correct (slopes flash, plains inundate).

## Task 2 — validation vs 17-yr climatology (SAME month vs SAME month)

The Task-1 footprint of the report issued in month *M* is compared against the
historical climatology of **that same calendar month *M* only** (not the
6-month horizon): Jan report → Jan history, Aug report → Aug history.
Outputs: `output/_validation_summary.csv`,
`_agreement_byreport.csv`, `_persistence_vs_history.csv`;
maps `figures/vs_retro/agreement_monthMM.png` + `_contact_agreement.png`;
chart `persistence_vs_history.png`.

Agreement classes: **BOTH**, **FORECAST_ONLY** (flagged, no history that month),
**HISTORY_ONLY** (history that month, not flagged), **NEITHER**.

**Headline (2023–2025 reports pooled, Tambon-months):**
- Precision — of forecast-flagged, **34 %** historically flood *in that month*.
- Recall — of that month's historical floods, **59 %** are forecast-flagged.
- **Recall of historically HIGH-risk Tambons: 85–100 %** in the months where
  high risk exists (**only Aug–Dec**; Jan–Jul have no level-3 Tambons, hence the
  blank cells). The forecast still almost never misses a chronic flood zone.

**Precision is strongly seasonal** (Jan 0.21 · Feb 0.03 · Apr 0.04 · Aug 0.46 ·
Oct 0.62 · **Nov 0.80**). This is the key caveat of strict same-month alignment:
a report issued in month *M* mostly warns about the **coming** wet-season months
(*M+1…M+5*), but here it is only credited against month *M* itself. So early-dry-
month reports look like heavy over-warning (large purple FORECAST_ONLY area) when
they are really forecasting *later* months — those hits are simply not counted in
month *M*. Precision therefore rises as the report month moves into the wet season
and the "next 6 months" increasingly *is* the current flood season.

> If you want to remove this forward-looking artifact entirely, align by **target
> month** instead (forecast *for* month *T* vs history *for* month *T*); the
> single-month `hist_window(hist, [m])` call in `03_validate_vs_history.py` is the
> one place that controls this.

**Persistence vs history** (`persistence_vs_history.png`) — persistence is now
1, 2, or 3 years, and the jump at 3/3 is sharp:

| Task-1 persistence | hist high | hist medium | hist none | mean floods/17yr |
|---|---|---|---|---|
| flagged 1 yr (new)    | 0.6 %  | 8 %  | 74 % | 0.75 |
| flagged 2 yr          | 0.7 %  | 8 %  | 70 % | 0.83 |
| flagged 3 yr (always) | 12.1 % | 11 % | 54 % | 2.33 |

Tambons flagged in **all 3** years are ~20× more likely to be historically
high-risk and flood ~3× as often as one-off flags — so Task-1's dark "always"
colour still tracks genuine chronic risk. The absolute levels look low only
because of the same-month artifact above (much of an "always" area's true history
lands in *later* months); slice `_agreement_byreport.csv` by `ISSUE_MONTH`
for the per-month picture, or switch to target-month alignment to see it cleanly.

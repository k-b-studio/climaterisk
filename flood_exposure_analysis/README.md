# Thailand Flood Exposure Analysis (2019–2025)

Source: DDPM flood statistics, `/IECC/Flood Historical Data/` — files
`gd027_flood_stat2562…2568_final.xlsx` (BE 2562–2568 = 2019–2025).

## How to reproduce

```bash
python3 01_clean_prepare.py      # -> data/province_year.csv, data/district_year.csv
python3 02_analyze_visualize.py  # -> output/*.csv, figures/*.png
```

## 1. Data cleaning & preparation (`01_clean_prepare.py`)

Each year's file has a **different schema** (province aggregates in 2562/2568,
district-event records in 2563–2565, village-level records in 2566–2567).
All years are harmonized to one row per **province × year** with 19 common
exposure dimensions (events, geographic extent, people/households affected,
evacuations, deaths/missing/injured, housing, business, agriculture-rai,
livestock, fisheries, transport, infrastructure, damage-THB).

Cleaning steps applied:
- dropped Thai-label sub-header rows and multi-row merged headers (dynamic header detection)
- dropped subtotal rows: `"<จังหวัด> รวม"`, `"รวมทั้งหมด …"`, region `"ผลรวม"` rows,
  and 2565's hidden per-province total rows (อำเภอ column holding a numeric district
  count — these exactly duplicated the district detail and would have doubled 2022)
- numeric coercion (thousand separators, blanks, `-`), whitespace/newline normalization,
  province-name normalization → validated against the official 77-province list

## 2. Outputs

| File | Content |
|---|---|
| `data/province_year.csv` | 493 province×year rows, 19 dimensions |
| `data/district_year.csv` | 3,212 district×year rows (2020–2024, where detail exists) |
| `output/province_risk_levels.csv` | all 77 provinces: composite score, components, 5-level risk |
| `output/top20_provinces_composite.csv` | top-20 provinces by composite exposure |
| `output/top20_provinces_by_dimension.csv` | top-20 per dimension |
| `output/top20_districts.csv` | top-20 districts by affected people |
| `output/national_yearly_exposure.csv` | national totals per dimension per year |
| `output/national_projection_2026_2028.csv` | linear-trend projection ±1 SE |
| `figures/1…6_*.png` | charts (top-20, per-dimension, districts, trend+projection, heatmap, risk levels) |

## 3. Methodology

**Composite exposure score (0–100).** Per province, dimensions are summed over
2019–2025, log1p-transformed, min-max normalized, then combined:
human impact 30% (people + households) · life-safety 20% (deaths, injured, evacuees)
· property 20% (housing + business) · agriculture 10% (crops, livestock, fisheries)
· infrastructure 10% (transport + public sites) · frequency 10% (years affected / 7).

**5 risk levels.** Quintiles of the composite score → Very Low / Low / Moderate /
High / Very High (~15–16 provinces per level).

**Projection.** OLS linear trend on national yearly totals, projected to 2026–2028
with ±1 SE band. Flood exposure is highly volatile (2022 and 2025 were extreme
years); treat the projection as a trend indication, not a forecast.

## 4. Key findings

- **Top provinces (composite):** นครราชสีมา (100), พัทลุง (92.5), เชียงราย (89.3),
  นครศรีธรรมราช (88.3), สงขลา (88.1), เชียงใหม่ (87.9), ขอนแก่น, นราธิวาส, สุโขทัย, ยะลา.
  The Very-High tier is dominated by the **lower North (Chiang Mai/Chiang Rai)**,
  the **Northeast (Korat plateau)** and the **deep South (Songkhla–Pattani–Narathiwat–Phatthalung)**.
- **Top districts:** แม่แจ่ม and อมก๋อย (เชียงใหม่), เมืองนครศรีธรรมราช, เมืองชัยภูมิ,
  หาดใหญ่ (สงขลา), เมืองพัทลุง, ระแงะ (นราธิวาส).
- **Trend:** affected people rose from ~1.8M (2019) to ~6.7M (2025); deaths hit a
  record 272 in 2025. The linear trend projects ~5.3–6.2M affected people per year
  for 2026–2028, with housing damage trending up most steeply; agriculture damage
  trends down (peak was the 2021–2022 Chao Phraya/Mun basin floods).
- **Risk classification:** 15 provinces Very High, 16 High — together ~40% of
  provinces carry the bulk of national flood exposure.

## 5. Caveats

- Monetary damage (THB) exists only in the 2562 file — cross-year comparison uses
  physical counts instead.
- 2563–2565 extent counts (tambon/village) are sums over events and can double-count
  repeatedly-hit areas; 2566–2567 use unique village/subdistrict codes.
- 2566 source only covers 74 provinces; 2562 covers 60 (smaller flood year).
- Occasional source inconsistencies remain (e.g., households > people in a few
  2568 rows) — kept as reported by DDPM.

# P0 Financial Entity Normalization

**Generated**: 2026-06-21 04:58

## 1. Executive Summary

| Metric | Value |
|---|---:|
| Raw P0 candidates (from scoring) | 8 |
| Duplicates merged | 2 → 1 (Tax Relief Advocates + TRA) |
| Normalized P0 entities | 7 |
| test\_now count | 5 |
| research\_only count | 1 |
| do\_not\_test\_now count | 1 |

## 2. Normalized P0 Entities

| Entity | Aliases | Vertical | Combined Dets | Combined Stns | Avg Score | Avg Risk |
|:---|---:|:---:|---:|---:|---:|---:|
| Tax Relief Advocates | Tax Relief Advocates (TRA), TRA | tax_relief | 50 | 8 | 14.5 | 3.5 |
| Optima Tax Relief | — | tax_relief | 28 | 3 | 14.8 | 3.5 |
| Ethos | — | insurance | 52 | 9 | 14.0 | 3.0 |
| Coast One Tax Group | — | tax_relief | 10 | 3 | 13.8 | 3.5 |
| SuperSure Insurance | SuperSure Insurance Agency, LLC, SuperSure Insurance Agency LLC, SuperSure, Super Sure Insurance Agency LLC | insurance | 23 | 4 | 13.3 | 3.0 |
| LifeLock | Lifelock | identity_protection | 50 | 5 | 13.0 | 2.5 |
| Amco | — | other | 16 | 1 | 13.5 | 3.5 |

## 3. Duplicate Resolution Notes

### Tax Relief Advocates + TRA

- **Evidence**: Identical phone numbers (`800-503-7944`, `800-550-8178`, `800-575-9379`, etc.) across both records
- **Evidence**: Same `sample_offer` theme: "IRS tax debt relief" / "eliminate or reduce tax debt with IRS programs"
- **Evidence**: Same vertical classification: `tax_relief`
- **Decision**: Merged into single entity with combined 50 detections across 7 stations
- **Official site**: tra.com

### Amco Reclassification

- **Current vertical**: `tax_relief` (original classification)
- **Evidence**: Sample offer "finance repairs, limited time offer" — likely AAMCO auto repair financing
- **Decision**: Reclassified as `other` / `do_not_test_now`. Not a consumer financial brand.

### Coast One Tax Group Reclassification

- **Current vertical**: `debt_relief` (original classification)
- **Evidence**: coastonetaxgroup.com is a tax resolution firm (IRS tax debt, $10K+ minimum)
- **Decision**: Reclassified as `tax_relief`

### SuperSure Insurance — B2B Caveat

- **Current vertical**: `insurance`
- **Evidence**: supersure.com is a business insurance brokerage (commercial P&C, employee benefits)
- **Decision**: NOT consumer insurance. Marked `research_only` — not suitable for standard consumer affiliate/leadgen offers.

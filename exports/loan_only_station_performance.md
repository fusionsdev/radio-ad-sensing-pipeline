# Loan-Only Station Performance Report

**Generated**: 2026-06-21 05:19
**Source**: Live Docker DB — full detection history

## Executive Summary

| Metric | Value |
|---|---:|
| Active stations analyzed | 10 |
| Keep (2+ loan advertisers) | 8 |
| Watch (1 loan advertiser) | 1 |
| Rotate out (0 loan advertisers) | 1 |
| Total loan detections | 64 |
| Total non-loan detections | 4033 |

## Station Performance Table

| Station | Market | Total | Loan Ads | Unique Loan | Irrelevant | Loan Rate | Decision | Reason |
|:---|---:|---:|---:|---:|---:|---:|:---|:---|
| wsb-am-750 | Atlanta, GA | 589 | 15 | 6 | 574 | 2.5% | ✅ keep | 6 unique loan advertisers, 15 loan detections |
| wbap-am-820 | Dallas–Fort Worth, TX | 514 | 13 | 8 | 501 | 2.5% | ✅ keep | 8 unique loan advertisers, 13 loan detections |
| klif-am-570 | Dallas, TX | 470 | 12 | 9 | 458 | 2.6% | ✅ keep | 9 unique loan advertisers, 12 loan detections |
| ktrh-am-740 | Houston, TX | 432 | 10 | 6 | 422 | 2.3% | ✅ keep | 6 unique loan advertisers, 10 loan detections |
| wibc-fm-931 | Indianapolis, IN | 445 | 5 | 4 | 440 | 1.1% | ✅ keep | 4 unique loan advertisers, 5 loan detections |
| woai-am-1200 | San Antonio, TX | 571 | 3 | 3 | 568 | 0.5% | ✅ keep | 3 unique loan advertisers, 3 loan detections |
| kabc-am-790 | Los Angeles, CA | 380 | 2 | 2 | 378 | 0.5% | ✅ keep | 2 unique loan advertisers, 2 loan detections |
| whbo-1040 | Tampa, FL | 485 | 2 | 2 | 483 | 0.4% | ✅ keep | 2 unique loan advertisers, 2 loan detections |
| wwtn-fm-997 | Nashville, TN | 161 | 2 | 1 | 159 | 1.2% | 👁️ watch | Only 1 loan advertiser. Monitor for 24-48h. |
| wtam-am-1100 | Cleveland, OH | 50 | 0 | 0 | 50 | 0.0% | ❌ rotate_out | 0 loan ads after 50 total detections. Low loan signal. |

## Keep Stations

### kabc-am-790 — KABC 790 AM — Los Angeles, CA

- **Loan ads**: 2 / 380 total (0.5%)
- **Unique loan advertisers**: 2
- **Advertisers**: Albert, unnamed_detection_3922

### klif-am-570 — KLIF 570 AM — Dallas, TX

- **Loan ads**: 12 / 470 total (2.6%)
- **Unique loan advertisers**: 9
- **Advertisers**: American Financing, American financing, Bills Happen, BillsHappen.com, Billshappen, Goldco, National Debt Relief, U.S. Tax Shield

### ktrh-am-740 — KTRH 740 AM — Houston, TX

- **Loan ads**: 10 / 432 total (2.3%)
- **Unique loan advertisers**: 6
- **Advertisers**: Albert, American Financing, BillsHappen.com, Billshappen.com, Debt Relief Advocates, unnamed_detection_3551

### wbap-am-820 — WBAP 820 AM — Dallas–Fort Worth, TX

- **Loan ads**: 13 / 514 total (2.5%)
- **Unique loan advertisers**: 8
- **Advertisers**: American Financing, Coast One Financial Group, Coast One Financial Group, U.S. Tax Shield, Coast One Tax Group, Optima Tax Relief, Tax Relief Advocates (TRA), U.S. Tax Shield, unnamed_detection_483

### whbo-1040 — WHBO 1040 AM — Tampa, FL

- **Loan ads**: 2 / 485 total (0.4%)
- **Unique loan advertisers**: 2
- **Advertisers**: Coast One Financial Group, U.S. Tax Shield, Coast One Tax Group

### wibc-fm-931 — WIBC 93.1 FM — Indianapolis, IN

- **Loan ads**: 5 / 445 total (1.1%)
- **Unique loan advertisers**: 4
- **Advertisers**: BillsHappen.com, Billshappen.com Lenders, Debt Relief Advocates, Mark Deal Realty

### woai-am-1200 — WOAI 1200 AM — San Antonio, TX

- **Loan ads**: 3 / 571 total (0.5%)
- **Unique loan advertisers**: 3
- **Advertisers**: American Financing, BillsHappen.com, Billshappen.com

### wsb-am-750 — WSB 750 AM — Atlanta, GA

- **Loan ads**: 15 / 589 total (2.5%)
- **Unique loan advertisers**: 6
- **Advertisers**: American Financing, Billshappen, Debt Relief Advocates, Endurance, Optima Tax Relief, unnamed_detection_3371


## Watch Stations

### wwtn-fm-997 — WWTN 99.7 FM — Nashville, TN

- **Only loan advertiser**: American Financing
- **Loan ads**: 2 / 161 total
- **Action**: Let run 24-48h, reassess. If no second loan advertiser appears, rotate out.


## Rotate Out Stations

### wtam-am-1100 — WTAM 1100 AM — Cleveland, OH

- **Total ads**: 50 (all non-loan)
- **Irrelevant ads**: 50
- **Reason**: 0 loan ads after 50 total detections. Low loan signal.


## Loan Advertisers Found

**Total unique loan advertisers across all stations**: 25

- Albert → kabc-am-790, ktrh-am-740
- American Financing → klif-am-570, ktrh-am-740, wbap-am-820, woai-am-1200, wsb-am-750, wwtn-fm-997
- American financing → klif-am-570
- Bills Happen → klif-am-570
- BillsHappen.com → klif-am-570, ktrh-am-740, wibc-fm-931, woai-am-1200
- Billshappen → klif-am-570, wsb-am-750
- Billshappen.com → ktrh-am-740, woai-am-1200
- Billshappen.com Lenders → wibc-fm-931
- Coast One Financial Group → wbap-am-820, whbo-1040
- Coast One Financial Group, U.S. Tax Shield → wbap-am-820
- Coast One Tax Group → wbap-am-820
- Debt Relief Advocates → ktrh-am-740, wibc-fm-931, wsb-am-750
- Endurance → wsb-am-750
- Goldco → klif-am-570
- Mark Deal Realty → wibc-fm-931
- National Debt Relief → klif-am-570
- Optima Tax Relief → wbap-am-820, wsb-am-750
- Tax Relief Advocates (TRA) → wbap-am-820
- U.S. Tax Shield → klif-am-570, wbap-am-820
- U.S. Tax Shield, Coast One Tax Group → whbo-1040
- unnamed_detection_2680 → klif-am-570
- unnamed_detection_3371 → wsb-am-750
- unnamed_detection_3551 → ktrh-am-740
- unnamed_detection_3922 → kabc-am-790
- unnamed_detection_483 → wbap-am-820

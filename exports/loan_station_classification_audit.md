# Loan Station Classification Audit

**Source**: Live Docker DB — re-classified with strict loan criteria

## Summary Table

| Station | Sampled | True Loan | Medical Fin | False Pos | Unknown | Precision | Decision |
|:---|---:|---:|---:|---:|---:|---:|:---|
| woai-am-1200 | 20 | 0 | 0 | 3 | 9 | 0.0% | ❌ RE-SCORE |
| wsb-am-750 | 13 | 2 | 0 | 4 | 1 | 15.4% | ❌ RE-SCORE |
| wibc-fm-931 | 20 | 2 | 0 | 3 | 6 | 10.0% | ❌ RE-SCORE |
| klif-am-570 | 12 | 2 | 0 | 3 | 1 | 16.7% | ❌ RE-SCORE |
| ktrh-am-740 | 15 | 4 | 0 | 1 | 7 | 26.7% | ❌ RE-SCORE |
| wtam-am-1100 | 5 | 0 | 0 | 0 | 4 | 0.0% | ❌ RE-SCORE |

## Detailed Audit Per Station

### woai-am-1200

- **Sampled**: 20 / 32 loan candidates
- **True loan**: 0 | **Medical/pet financing**: 0 | **False positive**: 3 | **Unknown**: 9
- **Precision**: 0.0%

| ❌ | false_positive | Kinetico of San Antonio | known non-loan advertiser: kinetico of san antonio |
| ❌ | false_positive | World Car Kia | known non-loan advertiser: world car kia |
| ❌ | home_service_not_loan | (unnamed) | matched 'roofing' in combined text |
| ❓ | unknown | Connecticut S A | has company 'connecticut s a' but no clear loan signal |
| ❓ | unknown | CF moto | has company 'cf moto' but no clear loan signal |
| ❌ | false_positive | Kia | known non-loan advertiser: kia |
| ❓ | unknown | (unnamed) | no clear signal |
| ❓ | unknown | (unnamed) | no clear signal |
| ❌ | auto_not_loan | (unnamed) | matched 'car financing' in combined text |
| ❓ | unknown | (unnamed) | no clear signal |
| ❓ | unknown | (unnamed) | no clear signal |
| ❌ | false_positive | Wilco Hyundai, World Car Hyundai North, World Car Hyundai South | known non-loan advertiser: wilco hyundai, world car hyundai north, world car hyundai south |
| ❌ | false_positive | KineticoSA | known non-loan advertiser: kineticosa |
| ❌ | supplement_not_loan | (unnamed) | matched 'viome' in combined text |
| ❓ | unknown | (unnamed) | no clear signal |
| ❓ | unknown | (unnamed) | no clear signal |
| ❌ | false_positive | Wilco Hyundai | known non-loan advertiser: wilco hyundai |
| ❓ | unknown | (unnamed) | no clear signal |
| ❌ | false_positive | Rock's Discount Vitamins, World Car Kia, CertaPro Painters, Precision Windows | known non-loan advertiser: rock's discount vitamins, world car kia, certapro painters, precision windows |
| ❌ | false_positive | Precision Windows | known non-loan advertiser: precision windows |

### wsb-am-750

- **Sampled**: 13 / 13 loan candidates
- **True loan**: 2 | **Medical/pet financing**: 0 | **False positive**: 4 | **Unknown**: 1
- **Precision**: 15.4%

| ❌ | legal_not_loan | Claims Chaser | matched 'attorney' in combined text |
| ❌ | false_positive | Endurance | known non-loan advertiser: endurance |
| ❌ | false_positive | Peach State Hardwood Floors, NG Turf, Breda Pest Management | known non-loan advertiser: peach state hardwood floors, ng turf, breda pest management |
| ❌ | false_positive | Peach State Hardwood Floors | known non-loan advertiser: peach state hardwood floors |
| ❌ | false_positive | Finley Roofing | known non-loan advertiser: finley roofing |
| ❌ | tax_relief_not_loan | Findlay Roofing | matched 'irs' in combined text |
| ❓ | unknown | Gemellus Automotive Group | has company 'gemellus automotive group' but no clear loan signal |
| 💰 | true_loan | Debt Relief Advocates | known loan advertiser: debt relief advocates |
| 💰 | true_loan | (unnamed) | loan pattern in offer: 'personal loan' |
| ❌ | nonprofit_not_loan | The National Foundation for Credit Counseling | matched 'foundation' in combined text |
| ❌ | false_positive | Loud Security Systems | known non-loan advertiser: loud security systems |
| ❌ | nonprofit_not_loan | Coosa Valley Credit Union | matched 'donate' in combined text |
| ❌ | false_positive | Finley Roofing | known non-loan advertiser: finley roofing |

### wibc-fm-931

- **Sampled**: 20 / 21 loan candidates
- **True loan**: 2 | **Medical/pet financing**: 0 | **False positive**: 3 | **Unknown**: 6
- **Precision**: 10.0%

| ❌ | tax_relief_not_loan | Upside-App | matched 'irs' in combined text |
| ❓ | unknown | (unnamed) | no clear signal |
| ❌ | false_positive | Hubler Toyota | known non-loan advertiser: hubler toyota |
| ❌ | false_positive | Thompson Furniture and Mattress | known non-loan advertiser: thompson furniture and mattress |
| ❓ | unknown | (unnamed) | no clear signal |
| ❌ | false_positive | Hubler | known non-loan advertiser: hubler |
| ❌ | false_positive | Hubler Toyota | known non-loan advertiser: hubler toyota |
| ❌ | false_positive | Farnsworth Metal Recycling and Raised Demolition | known non-loan advertiser: farnsworth metal recycling and raised demolition |
| ❓ | unknown | (unnamed) | no clear signal |
| ❌ | tax_relief_not_loan | (unnamed) | matched 'irs' in combined text |
| ❌ | false_positive | Hubler | known non-loan advertiser: hubler |
| ❓ | unknown | (unnamed) | no clear signal |
| ❓ | unknown | (unnamed) | no clear signal |
| ❌ | false_positive | Farnsworth Metal Recycling | known non-loan advertiser: farnsworth metal recycling |
| ❌ | false_positive | Knig Equipment | known non-loan advertiser: knig equipment |
| ❌ | false_positive | Ascension Island Mint | known non-loan advertiser: ascension island mint |
| ❓ | unknown | Mark Deal Realty | has company 'mark deal realty' but no clear loan signal |
| ❌ | nonprofit_not_loan | (unnamed) | matched 'foundation' in combined text |
| 💰 | true_loan | Debt Relief Advocates | known loan advertiser: debt relief advocates |
| 💰 | true_loan | Debt Relief Advocates | known loan advertiser: debt relief advocates |

### klif-am-570

- **Sampled**: 12 / 12 loan candidates
- **True loan**: 2 | **Medical/pet financing**: 0 | **False positive**: 3 | **Unknown**: 1
- **Precision**: 16.7%

| ❌ | false_positive | Mark Spain Real Estate, Empower Home Team | known non-loan advertiser: mark spain real estate, empower home team |
| ❌ | false_positive | Maritz Kia | known non-loan advertiser: maritz kia |
| ❌ | false_positive | Freeman Toyota and Hurst | known non-loan advertiser: freeman toyota and hurst |
| ❌ | tax_relief_not_loan | (unnamed) | matched 'tax' in combined text |
| ❌ | false_positive | Freeman Toyota | known non-loan advertiser: freeman toyota |
| ❌ | tax_relief_not_loan | Upside | matched 'tax' in combined text |
| ❓ | unknown | (unnamed) | no clear signal |
| 💰 | true_loan | (unnamed) | loan pattern in transcript: 'personal loan' |
| ❌ | false_positive | LensSeek | known non-loan advertiser: lensseek |
| ❌ | tax_relief_not_loan | Upside | matched 'irs' in combined text |
| ❌ | false_positive | Ghost Bed | known non-loan advertiser: ghost bed |
| 💰 | true_loan | American Financing | known loan advertiser: american financing |

### ktrh-am-740

- **Sampled**: 15 / 15 loan candidates
- **True loan**: 4 | **Medical/pet financing**: 0 | **False positive**: 1 | **Unknown**: 7
- **Precision**: 26.7%

| ❓ | unknown | (unnamed) | no clear signal |
| ❌ | legal_not_loan | Retailmyride.com, CarPro Jerry Reynolds, Auto Design Specialty (ADS) | matched 'sue' in combined text |
| ❓ | unknown | Albert | has company 'albert' but no clear loan signal |
| ❓ | unknown | Albert | has company 'albert' but no clear loan signal |
| ❌ | false_positive | Discover | known non-loan advertiser: discover |
| ❓ | unknown | (unnamed) | no clear signal |
| 💰 | true_loan | American Financing | known loan advertiser: american financing |
| ❓ | unknown | (unnamed) | no clear signal |
| 💰 | true_loan | Debt Relief Advocates | known loan advertiser: debt relief advocates |
| 💰 | true_loan | Billshappen.com | known loan advertiser: billshappen.com |
| 💰 | true_loan | American Financing | known loan advertiser: american financing |
| ❓ | unknown | (unnamed) | no clear signal |
| ❓ | unknown | (unnamed) | no clear signal |
| ❌ | false_positive | Allied Signing and Windows | known non-loan advertiser: allied signing and windows |
| ❌ | false_positive | Capital One | known non-loan advertiser: capital one |

### wtam-am-1100

- **Sampled**: 5 / 5 loan candidates
- **True loan**: 0 | **Medical/pet financing**: 0 | **False positive**: 0 | **Unknown**: 4
- **Precision**: 0.0%

| ❓ | unknown | (unnamed) | no clear signal |
| ❓ | unknown | (unnamed) | no clear signal |
| ❓ | unknown | (unnamed) | no clear signal |
| ❌ | false_positive | I Heart Radio | known non-loan advertiser: i heart radio |
| ❓ | unknown | (unnamed) | no clear signal |

## Revised Rotation Recommendations

Based on audit precision:

| Station | Original Decision | Audited Precision | Revised Decision |
|:---|---:|---:|:---|
| woai-am-1200 | keep | 0.0% | re-score |
| wsb-am-750 | keep | 15.4% | re-score |
| wibc-fm-931 | keep | 10.0% | re-score |
| klif-am-570 | keep | 16.7% | re-score |
| ktrh-am-740 | keep | 26.7% | re-score |
| wtam-am-1100 | rotate_out | 0.0% | re-score |

## Common False Positive Patterns

- **tax_relief_not_loan**: 6 occurrences
- **nonprofit_not_loan**: 3 occurrences
- **legal_not_loan**: 2 occurrences
- **home_service_not_loan**: 1 occurrences
- **auto_not_loan**: 1 occurrences
- **supplement_not_loan**: 1 occurrences

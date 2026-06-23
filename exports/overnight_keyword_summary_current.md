# Keyword Candidates — Current (live radio-worker DB)

Generated: 2026-06-20T00:47:52Z

## Source identity
- db: `/app/data/pipeline.db` (radio-worker container, `pipeline_data` named volume)
- detections: **3200** · chunks_done: **14726**
- candidates: **449** (radio_transcript: 11 · seed: 438)

## Candidates by source_type
- cfpb_complaint: 438
- radio_transcript: 11

## Candidates by variant_type
- brand: 76
- alternative: 74
- complaints: 74
- reviews: 74
- bbb: 73
- phone_number: 73
- product: 3
- intent: 1
- contact: 1

## Candidates by status
- approved_seed: 252
- new: 197

## Real radio advertisers (source_type = radio_transcript)

| # | keyword | variant | status | score | entity |
|---|---------|---------|--------|-------|--------|
| 1 | bills happen | brand | new | 92.0 | Billshappen.com |
| 2 | bills happen loans | product | new | 92.0 | Billshappen.com |
| 3 | billshappen | brand | new | 92.0 | Billshappen.com |
| 4 | billshappen alternative | alternative | new | 92.0 | Billshappen.com |
| 5 | billshappen complaints | complaints | new | 92.0 | Billshappen.com |
| 6 | billshappen legit | intent | new | 92.0 | Billshappen.com |
| 7 | billshappen loans | product | new | 92.0 | Billshappen.com |
| 8 | billshappen personal loan | product | new | 92.0 | Billshappen.com |
| 9 | billshappen phone number | contact | new | 92.0 | Billshappen.com |
| 10 | billshappen reviews | reviews | new | 92.0 | Billshappen.com |
| 11 | billshappen.com | brand | new | 92.0 | Billshappen.com |

## Top seed candidates (CFPB)

| # | keyword | variant | source | status | score |
|---|---------|---------|--------|--------|-------|
| 1 | jpmorgan chase & | brand | cfpb_complaint | approved_seed | 100.0 |
| 2 | jpmorgan chase & alternative | alternative | cfpb_complaint | approved_seed | 100.0 |
| 3 | jpmorgan chase & bbb | bbb | cfpb_complaint | approved_seed | 100.0 |
| 4 | jpmorgan chase & complaints | complaints | cfpb_complaint | approved_seed | 100.0 |
| 5 | jpmorgan chase & phone number | phone_number | cfpb_complaint | approved_seed | 100.0 |
| 6 | jpmorgan chase & reviews | reviews | cfpb_complaint | approved_seed | 100.0 |
| 7 | santander holdings usa | brand | cfpb_complaint | approved_seed | 100.0 |
| 8 | santander holdings usa alternative | alternative | cfpb_complaint | approved_seed | 100.0 |
| 9 | santander holdings usa bbb | bbb | cfpb_complaint | approved_seed | 100.0 |
| 10 | santander holdings usa complaints | complaints | cfpb_complaint | approved_seed | 100.0 |
| 11 | santander holdings usa phone number | phone_number | cfpb_complaint | approved_seed | 100.0 |
| 12 | santander holdings usa reviews | reviews | cfpb_complaint | approved_seed | 100.0 |
| 13 | wells fargo & | brand | cfpb_complaint | approved_seed | 100.0 |
| 14 | wells fargo & alternative | alternative | cfpb_complaint | approved_seed | 100.0 |
| 15 | wells fargo & bbb | bbb | cfpb_complaint | approved_seed | 100.0 |
| 16 | wells fargo & complaints | complaints | cfpb_complaint | approved_seed | 100.0 |
| 17 | wells fargo & phone number | phone_number | cfpb_complaint | approved_seed | 100.0 |
| 18 | wells fargo & reviews | reviews | cfpb_complaint | approved_seed | 100.0 |
| 19 | block | brand | cfpb_complaint | approved_seed | 99.0 |
| 20 | block alternative | alternative | cfpb_complaint | approved_seed | 99.0 |
| 21 | block bbb | bbb | cfpb_complaint | approved_seed | 99.0 |
| 22 | block complaints | complaints | cfpb_complaint | approved_seed | 99.0 |
| 23 | block phone number | phone_number | cfpb_complaint | approved_seed | 99.0 |
| 24 | block reviews | reviews | cfpb_complaint | approved_seed | 99.0 |
| 25 | coinbase | brand | cfpb_complaint | approved_seed | 99.0 |

---
_`radio_transcript` = real over-the-air advertiser captured. `cfpb_complaint` = seed expansion (synthetic, not from radio)._
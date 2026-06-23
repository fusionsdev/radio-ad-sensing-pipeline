# #0009 USPTO verification tests fail on Justia filename serial parsing and case-sensitive dry-run assertion

- 2026-06-23T14:27:53Z `issue`: USPTO verification tests fail on Justia filename serial parsing and case-sensitive dry-run assertion [tests/test_uspto_verification.py:29]
- 2026-06-23T14:28:37Z `attempt`: Aligned USPTO Justia serial parser with filename serial URLs and made dry-run goods_services assertion case-insensitive [scripts/verify_apify_candidates_uspto.py] (worked)
- 2026-06-23T14:31:26Z `fix`: USPTO verifier serial parser matches Justia filename serials and dry-run assertion is case-insensitive; tests pass [scripts/verify_apify_candidates_uspto.py]

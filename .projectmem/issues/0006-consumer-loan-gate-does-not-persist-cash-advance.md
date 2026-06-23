# #0006 consumer loan gate does not persist cash advance keyword when transcript contains loan intent

- 2026-06-23T13:53:25Z `issue`: consumer loan gate does not persist cash advance keyword when transcript contains loan intent [tests/test_consumer_personal_loan_gating.py:123]
- 2026-06-23T13:54:29Z `attempt`: Added cash advance to live vertical keyword scan config so accepted consumer-loan cash advance transcripts can persist keyword_hits [config/vertical_keywords.yaml] (worked)

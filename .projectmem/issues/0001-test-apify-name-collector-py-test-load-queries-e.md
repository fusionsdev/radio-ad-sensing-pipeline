# #0001 test_apify_name_collector.py::test_load_queries expects 150 Apify queries but current fixture loads 1200

- 2026-06-23T13:23:05Z `issue`: test_apify_name_collector.py::test_load_queries expects 150 Apify queries but current fixture loads 1200 [tests/test_apify_name_collector.py:14]
- 2026-06-23T13:23:58Z `attempt`: Updated test_load_queries to derive expected count from non-comment config rows instead of fixed 150 [tests/test_apify_name_collector.py] (worked)

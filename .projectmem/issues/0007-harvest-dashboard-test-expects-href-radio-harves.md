# #0007 harvest dashboard test expects href=/radio-harvest self-link that current control panel no longer renders

- 2026-06-23T13:55:26Z `issue`: harvest dashboard test expects href=/radio-harvest self-link that current control panel no longer renders [tests/test_harvest_dashboard.py:255]
- 2026-06-23T13:55:59Z `attempt`: Updated harvest dashboard control-panel test to assert current status/detections links instead of obsolete self-link [tests/test_harvest_dashboard.py] (worked)
- 2026-06-23T14:31:13Z `fix`: harvest dashboard test now asserts current control-panel links; focused and full pytest pass [tests/test_harvest_dashboard.py]

# #0008 test_live_events_sse hangs because TestClient waits on infinite /api/live/events stream teardown

- 2026-06-23T14:26:29Z `issue`: test_live_events_sse hangs because TestClient waits on infinite /api/live/events stream teardown [tests/test_radiosense_api.py:67]
- 2026-06-23T14:27:06Z `attempt`: Added once=true bounded SSE mode and updated live events test to avoid infinite stream teardown hang [dashboard/routes/radiosense.py] (worked)
- 2026-06-23T14:31:19Z `fix`: live events SSE supports once=true for bounded test/probe response; API tests and full pytest pass [dashboard/routes/radiosense.py]

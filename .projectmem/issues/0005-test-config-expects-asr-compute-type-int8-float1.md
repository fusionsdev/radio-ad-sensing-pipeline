# #0005 test_config expects asr_compute_type int8_float16 but repository settings load float16

- 2026-06-23T13:52:23Z `issue`: test_config expects asr_compute_type int8_float16 but repository settings load float16 [tests/test_config.py:34]
- 2026-06-23T13:52:58Z `attempt`: Updated repo config test to expect committed ASR compute_type float16 instead of stale int8_float16 [tests/test_config.py] (worked)
- 2026-06-23T14:30:56Z `fix`: config test now matches committed float16 ASR compute_type; focused and full pytest pass [tests/test_config.py]

# #0002 extract_serial_from_url fails to parse Justia trademark URLs with serial in filename

- 2026-06-23T13:34:36Z `issue`: extract_serial_from_url fails to parse Justia trademark URLs with serial in filename [scripts/discover_justia_names_via_apify.py:28]
- 2026-06-23T13:34:50Z `attempt`: Updated Justia serial parser to extract 7-8 digit serials from slug filenames and bare path segments [scripts/discover_justia_names_via_apify.py] (worked)
- 2026-06-23T14:30:33Z `fix`: Justia collector serial parser now extracts filename serials; focused and full pytest pass [scripts/discover_justia_names_via_apify.py]

# #0003 extract_slug_name parses Justia numeric path segment instead of mark slug filename

- 2026-06-23T13:35:04Z `issue`: extract_slug_name parses Justia numeric path segment instead of mark slug filename [scripts/discover_justia_names_via_apify.py:39]
- 2026-06-23T13:35:16Z `attempt`: Updated Justia slug parser to derive mark slug from final .html filename and strip trailing serial [scripts/discover_justia_names_via_apify.py] (worked)
- 2026-06-23T14:30:40Z `fix`: Justia collector slug parser now extracts final filename slug; focused and full pytest pass [scripts/discover_justia_names_via_apify.py]

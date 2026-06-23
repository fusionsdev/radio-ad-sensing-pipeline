# #0004 audit_keyword_hits_verticals flags personal loan as polluted and deletes two rows instead of one

- 2026-06-23T13:50:54Z `issue`: audit_keyword_hits_verticals flags personal loan as polluted and deletes two rows instead of one [tests/test_audit_keyword_hits_verticals.py:58]
- 2026-06-23T13:51:53Z `attempt`: Changed keyword_hits audit so exact consumer loan target phrases are not polluted solely by legacy loan vertical mapping [shared/keyword_hits_audit.py] (worked)

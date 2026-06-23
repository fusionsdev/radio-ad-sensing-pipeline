# Keyword Triage Report

**Source:** `exports/keyword_candidates_current.csv` (449 candidates · 11 radio_transcript · 438 cfpb_complaint seed)

## 1. Executive Summary

- **Total keywords:** 449
- **approve_for_ads:** 3
- **approve_for_research:** 22
- **hold_for_manual_review:** 53
- **reject:** 371

**Top 10 keywords (by commercial value + pipeline score):**

1. `bills happen` — hold_for_manual_review (value 5/5)
2. `bills happen loans` — approve_for_ads (value 5/5)
3. `billshappen` — hold_for_manual_review (value 5/5)
4. `billshappen loans` — approve_for_ads (value 5/5)
5. `billshappen personal loan` — approve_for_ads (value 5/5)
6. `billshappen.com` — hold_for_manual_review (value 5/5)
7. `fc holdco` — hold_for_manual_review (value 4/5)
8. `onemain finance` — hold_for_manual_review (value 4/5)
9. `clgf holdco 1` — hold_for_manual_review (value 4/5)
10. `billshappen alternative` — approve_for_research (value 4/5)

## 2. Keyword Decision Table

| keyword | intent | value_score | risk_level | recommended_action | match_type | ad_group | reason |
|---|---:|---:|---|---|---|---|---|
| bills happen | brand/trademark intent | 5 | trademark; misleading if impersonating | hold_for_manual_review | exact | Brand Intent — Billshappen | Verified radio personal-loan advertiser; high brand search volume; trademark review before ad copy |
| bills happen loans | direct loan intent | 5 | trademark; policy | approve_for_ads | phrase | Brand Intent — Billshappen | Product + brand from live radio ad; direct personal-loan intent; launch with comparison LP + trademark-safe copy |
| billshappen | brand/trademark intent | 5 | trademark; misleading if impersonating | hold_for_manual_review | exact | Brand Intent — Billshappen | Verified radio personal-loan advertiser; high brand search volume; trademark review before ad copy |
| billshappen alternative | problem-aware intent | 4 | trademark; misleading-risk | approve_for_research | phrase | Brand Intent — Billshappen | Comparison intent against known radio advertiser; test competitor/alternative LP |
| billshappen complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| billshappen legit | problem-aware intent | 4 | misleading-risk | approve_for_research | phrase | Brand Intent — Billshappen | Legitimacy research intent; funnel to comparison/review LP not impersonation |
| billshappen loans | direct loan intent | 5 | trademark; policy | approve_for_ads | phrase | Brand Intent — Billshappen | Product + brand from live radio ad; direct personal-loan intent; launch with comparison LP + trademark-safe copy |
| billshappen personal loan | direct loan intent | 5 | trademark; policy | approve_for_ads | phrase | Brand Intent — Billshappen | Product + brand from live radio ad; direct personal-loan intent; launch with comparison LP + trademark-safe copy |
| billshappen phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (contact); zero loan acquisition intent |
| billshappen reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| billshappen.com | brand/trademark intent | 5 | trademark; misleading if impersonating | hold_for_manual_review | exact | Brand Intent — Billshappen | Verified radio personal-loan advertiser; high brand search volume; trademark review before ad copy |
| jpmorgan chase & | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| jpmorgan chase & alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| jpmorgan chase & bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| jpmorgan chase & complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| jpmorgan chase & phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| jpmorgan chase & reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| santander holdings usa | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| santander holdings usa alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| santander holdings usa bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| santander holdings usa complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| santander holdings usa phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| santander holdings usa reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| wells fargo & | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| wells fargo & alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| wells fargo & bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| wells fargo & complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| wells fargo & phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| wells fargo & reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| block | irrelevant | 1 | off-vertical | reject | — | — | Crypto/payments brand; no loan vertical fit |
| block alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| block bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| block complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| block phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| block reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| coinbase | irrelevant | 1 | off-vertical | reject | — | — | Crypto/payments brand; no loan vertical fit |
| coinbase alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| coinbase bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| coinbase complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| coinbase phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| coinbase reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| paypal | irrelevant | 1 | off-vertical | reject | — | — | Crypto/payments brand; no loan vertical fit |
| paypal alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| paypal bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| paypal complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| paypal phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| paypal reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| robinhood markets | irrelevant | 1 | off-vertical | reject | — | — | Crypto/payments brand; no loan vertical fit |
| robinhood markets alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| robinhood markets bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| robinhood markets complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| robinhood markets phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| robinhood markets reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| credit acceptance | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| credit acceptance alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| credit acceptance bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| credit acceptance complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| credit acceptance phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| credit acceptance reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| bridgecrest acceptance | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| bridgecrest acceptance alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| bridgecrest acceptance bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| bridgecrest acceptance complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| bridgecrest acceptance phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| bridgecrest acceptance reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| fc holdco | brand/trademark intent | 4 | trademark | hold_for_manual_review | exact | Brand Intent — Installment Loan | Known installment/personal lender; brand traffic monetizable via comparison LP |
| fc holdco alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — FC HoldCo LLC | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| fc holdco bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| fc holdco complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| fc holdco phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| fc holdco reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| freedom mortgage | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| freedom mortgage alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| freedom mortgage bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| freedom mortgage complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| freedom mortgage phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| freedom mortgage reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| i c system | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Debt / Tax Relief | Debt collector brand searches often precede debt relief/loan consolidation intent |
| i c system alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — I.C. System | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| i c system bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| i c system complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| i c system phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| i c system reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| mr cooper | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| mr cooper alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| mr cooper bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| mr cooper complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| mr cooper phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| mr cooper reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| onemain finance | brand/trademark intent | 4 | trademark | hold_for_manual_review | exact | Brand Intent — Installment Loan | Known installment/personal lender; brand traffic monetizable via comparison LP |
| onemain finance alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — OneMain Finance Corporat | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| onemain finance bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| onemain finance complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| onemain finance phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| onemain finance reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| rocket mortgage | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| rocket mortgage alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| rocket mortgage bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| rocket mortgage complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| rocket mortgage phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| rocket mortgage reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| select portfolio servicing | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| select portfolio servicing alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| select portfolio servicing bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| select portfolio servicing complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| select portfolio servicing phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| select portfolio servicing reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| shellpoint partners | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| shellpoint partners alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| shellpoint partners bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| shellpoint partners complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| shellpoint partners phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| shellpoint partners reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| ally financial | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| ally financial alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| ally financial bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| ally financial complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| ally financial phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| ally financial reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| capital one financial | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| capital one financial alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| capital one financial bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| capital one financial complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| capital one financial phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| capital one financial reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| fifth third financial | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| fifth third financial alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| fifth third financial bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| fifth third financial complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| fifth third financial phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| fifth third financial reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| equifax | irrelevant | 1 | trademark; off-vertical | reject | — | — | Credit bureau brand; credit monitoring intent not loan acquisition |
| equifax alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| equifax bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| equifax complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| equifax phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| equifax reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| clgf holdco 1 | brand/trademark intent | 4 | trademark | hold_for_manual_review | exact | Brand Intent — Installment Loan | Known installment/personal lender; brand traffic monetizable via comparison LP |
| clgf holdco 1 alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — CLGF Holdco 1 | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| clgf holdco 1 bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| clgf holdco 1 complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| clgf holdco 1 phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| clgf holdco 1 reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| encore capital | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Debt / Tax Relief | Debt collector brand searches often precede debt relief/loan consolidation intent |
| encore capital alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — ENCORE CAPITAL GROUP INC | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| encore capital bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| encore capital complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| encore capital phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| encore capital reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| transunion intermediate | irrelevant | 1 | trademark; off-vertical | reject | — | — | Credit bureau brand; credit monitoring intent not loan acquisition |
| transunion intermediate alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| transunion intermediate bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| transunion intermediate complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| transunion intermediate phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| transunion intermediate reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| u s bancorp | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| u s bancorp alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| u s bancorp bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| u s bancorp complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| u s bancorp phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| u s bancorp reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| new york community bancorp | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| new york community bancorp alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| new york community bancorp bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| new york community bancorp complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| new york community bancorp phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| new york community bancorp reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| citibank n a | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| citibank n a alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| citibank n a bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| citibank n a complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| citibank n a phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| citibank n a reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| chime financial | irrelevant | 1 | off-vertical | reject | — | — | Crypto/payments brand; no loan vertical fit |
| chime financial alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| chime financial bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| chime financial complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| chime financial phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| chime financial reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| american express | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| american express alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| american express bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| american express complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| american express phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| american express reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| sofi technologies | brand/trademark intent | 4 | trademark | hold_for_manual_review | exact | Brand Intent — Installment Loan | Known installment/personal lender; brand traffic monetizable via comparison LP |
| sofi technologies alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — SOFI TECHNOLOGIES | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| sofi technologies bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| sofi technologies complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| sofi technologies phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| sofi technologies reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| exeter finance | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| exeter finance alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| exeter finance bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| exeter finance complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| exeter finance phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| exeter finance reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| hyundai capital america | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| hyundai capital america alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| hyundai capital america bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| hyundai capital america complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| hyundai capital america phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| hyundai capital america reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| cl | brand/trademark intent | 4 | trademark | hold_for_manual_review | exact | Brand Intent — Installment Loan | Known installment/personal lender; brand traffic monetizable via comparison LP |
| cl alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — CL Holdings LLC | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| cl bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| cl complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| cl phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| cl reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| portfolio recovery associates | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Debt / Tax Relief | Debt collector brand searches often precede debt relief/loan consolidation intent |
| portfolio recovery associates alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — Portfolio Recovery Assoc | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| portfolio recovery associates bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| portfolio recovery associates complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| portfolio recovery associates phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| portfolio recovery associates reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| resurgent capital services l p | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Debt / Tax Relief | Debt collector brand searches often precede debt relief/loan consolidation intent |
| resurgent capital services l p alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — Resurgent Capital Servic | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| resurgent capital services l p bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| resurgent capital services l p complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| resurgent capital services l p phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| resurgent capital services l p reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| transworld systems | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Debt / Tax Relief | Debt collector brand searches often precede debt relief/loan consolidation intent |
| transworld systems alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — TRANSWORLD SYSTEMS INC | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| transworld systems bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| transworld systems complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| transworld systems phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| transworld systems reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| roundpoint mortgage servicing | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| roundpoint mortgage servicing alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| roundpoint mortgage servicing bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| roundpoint mortgage servicing complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| roundpoint mortgage servicing phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| roundpoint mortgage servicing reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| american honda finance | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| american honda finance alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| american honda finance bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| american honda finance complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| american honda finance phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| american honda finance reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| bread financial | brand/trademark intent | 4 | trademark | hold_for_manual_review | exact | Brand Intent — Installment Loan | Known installment/personal lender; brand traffic monetizable via comparison LP |
| bread financial alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — Bread Financial Holdings | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| bread financial bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| bread financial complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| bread financial phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| bread financial reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| experian information solutions | irrelevant | 1 | trademark; off-vertical | reject | — | — | Credit bureau brand; credit monitoring intent not loan acquisition |
| experian information solutions alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| experian information solutions bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| experian information solutions complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| experian information solutions phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| experian information solutions reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| loancare | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| loancare alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| loancare bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| loancare complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| loancare phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| loancare reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| westlake services | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| westlake services alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| westlake services bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| westlake services complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| westlake services phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| westlake services reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| bank of america national association | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| bank of america national association alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| bank of america national association bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| bank of america national association complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| bank of america national association phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| bank of america national association reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| navy federal credit union | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| navy federal credit union alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| navy federal credit union bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| navy federal credit union complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| navy federal credit union phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| navy federal credit union reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| td bank us holding | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| td bank us holding alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| td bank us holding bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| td bank us holding complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| td bank us holding phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| td bank us holding reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| discover bank | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| discover bank alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| discover bank bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| discover bank complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| discover bank phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| discover bank reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| ocwen financial | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| ocwen financial alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| ocwen financial bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| ocwen financial complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| ocwen financial phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| ocwen financial reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| transferwise | irrelevant | 1 | off-vertical | reject | — | — | Crypto/payments brand; no loan vertical fit |
| transferwise alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| transferwise bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| transferwise complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| transferwise phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| transferwise reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| truist financial | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| truist financial alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| truist financial bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| truist financial complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| truist financial phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| truist financial reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| united services automobile association | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| united services automobile association alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| united services automobile association bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| united services automobile association complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| united services automobile association phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| united services automobile association reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| bmo bank national association | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| bmo bank national association alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| bmo bank national association bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| bmo bank national association complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| bmo bank national association phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| bmo bank national association reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| pnc bank n a | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| pnc bank n a alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| pnc bank n a bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| pnc bank n a complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| pnc bank n a phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| pnc bank n a reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| synchrony financial | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| synchrony financial alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| synchrony financial bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| synchrony financial complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| synchrony financial phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| synchrony financial reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| american credit acceptance | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| american credit acceptance alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| american credit acceptance bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| american credit acceptance complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| american credit acceptance phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| american credit acceptance reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| early warning services | irrelevant | 1 | off-vertical | reject | — | — | Crypto/payments brand; no loan vertical fit |
| early warning services alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| early warning services bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| early warning services complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| early warning services phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| early warning services reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| national credit systems | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Debt / Tax Relief | Debt collector brand searches often precede debt relief/loan consolidation intent |
| national credit systems alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — National Credit Systems | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| national credit systems bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| national credit systems complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| national credit systems phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| national credit systems reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| toyota motor credit | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| toyota motor credit alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| toyota motor credit bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| toyota motor credit complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| toyota motor credit phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| toyota motor credit reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| goldman sachs bank usa | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| goldman sachs bank usa alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| goldman sachs bank usa bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| goldman sachs bank usa complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| goldman sachs bank usa phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| goldman sachs bank usa reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| selene | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| selene alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| selene bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| selene complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| selene phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| selene reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| general motors financial | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| general motors financial alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| general motors financial bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| general motors financial complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| general motors financial phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| general motors financial reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| citizens financial | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| citizens financial alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| citizens financial bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| citizens financial complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| citizens financial phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| citizens financial reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| foris dax | irrelevant | 1 | off-vertical | reject | — | — | Crypto/payments brand; no loan vertical fit |
| foris dax alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| foris dax bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| foris dax complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| foris dax phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| foris dax reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| pennymac loan services | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| pennymac loan services alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| pennymac loan services bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| pennymac loan services complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| pennymac loan services phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| pennymac loan services reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| barclays bank delaware | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| barclays bank delaware alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| barclays bank delaware bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| barclays bank delaware complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| barclays bank delaware phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| barclays bank delaware reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| ld | brand/trademark intent | 4 | trademark | hold_for_manual_review | exact | Brand Intent — Installment Loan | Known installment/personal lender; brand traffic monetizable via comparison LP |
| ld alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — LD Holdings Group | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| ld bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| ld complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| ld phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| ld reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| bsi financial | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| bsi financial alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| bsi financial bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| bsi financial complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| bsi financial phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| bsi financial reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| carrington mortgage services | brand/trademark intent | 2 | trademark; off-vertical | reject | — | — | Mortgage servicer brand; outside personal/installment loan vertical |
| carrington mortgage services alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| carrington mortgage services bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| carrington mortgage services complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| carrington mortgage services phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| carrington mortgage services reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| byrider franchising | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| byrider franchising alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| byrider franchising bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| byrider franchising complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| byrider franchising phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| byrider franchising reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| huntington national bank the | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | exact | Brand Intent — Major Lenders | High volume brand terms; only viable with non-impersonation comparison funnel |
| huntington national bank the alternative | brand/trademark intent | 3 | trademark; policy | hold_for_manual_review | phrase | Brand Intent — Major Lenders | Bank alternative queries have volume but trademark + financial services policy risk |
| huntington national bank the bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| huntington national bank the complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| huntington national bank the phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| huntington national bank the reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| w&a intermediate | brand/trademark intent | 4 | trademark | hold_for_manual_review | exact | Brand Intent — Installment Loan | Known installment/personal lender; brand traffic monetizable via comparison LP |
| w&a intermediate alternative | problem-aware intent | 3 | trademark; misleading-risk | approve_for_research | phrase | Alternatives — W&A Intermediate Co. | Alternative/comparison SERP; affiliate-friendly if LP is honest comparison |
| w&a intermediate bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| w&a intermediate complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| w&a intermediate phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| w&a intermediate reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| nissan motor acceptance | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| nissan motor acceptance alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| nissan motor acceptance bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| nissan motor acceptance complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| nissan motor acceptance phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| nissan motor acceptance reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| carmax | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| carmax alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| carmax bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| carmax complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| carmax phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| carmax reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |
| carvana | brand/trademark intent | 1 | off-vertical | reject | — | — | Auto finance/dealer brand; not in target verticals |
| carvana alternative | brand/trademark intent | 2 | trademark | reject | — | — | Alternative query outside core loan vertical or low affiliate monetization |
| carvana bbb | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (bbb); zero loan acquisition intent |
| carvana complaints | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (complaints); zero loan acquisition intent |
| carvana phone number | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (phone_number); zero loan acquisition intent |
| carvana reviews | low intent / informational | 1 | low-quality traffic | reject | — | — | Support/navigational variant (reviews); zero loan acquisition intent |

## 3. Recommended Ad Groups

| ad_group | keywords | intent | suggested_landing_page_angle |
|---|---|---|---|
| Alternatives — Bread Financial Holdings | `bread financial alternative` | problem-aware intent | Honest lender comparison with disclosure-first copy |
| Alternatives — CL Holdings LLC | `cl alternative` | problem-aware intent | Installment lender alternatives |
| Alternatives — CLGF Holdco 1 | `clgf holdco 1 alternative` | problem-aware intent | Subprime installment alternatives |
| Alternatives — ENCORE CAPITAL GROUP INC | `encore capital alternative` | problem-aware intent | Honest lender comparison with disclosure-first copy |
| Alternatives — FC HoldCo LLC | `fc holdco alternative` | problem-aware intent | Installment lender alternatives |
| Alternatives — I.C. System | `i c system alternative` | problem-aware intent | Debt relief educational LP |
| Alternatives — LD Holdings Group | `ld alternative` | problem-aware intent | Installment/payday alternative comparison |
| Alternatives — National Credit Systems | `national credit systems alternative` | problem-aware intent | Debt relief comparison LP |
| Alternatives — OneMain Finance Corporat | `onemain finance alternative` | problem-aware intent | Honest lender comparison with disclosure-first copy |
| Alternatives — Portfolio Recovery Assoc | `portfolio recovery associates alternative` | problem-aware intent | Honest lender comparison with disclosure-first copy |
| Alternatives — Resurgent Capital Servic | `resurgent capital services l p alternative` | problem-aware intent | Honest lender comparison with disclosure-first copy |
| Alternatives — SOFI TECHNOLOGIES | `sofi technologies alternative` | problem-aware intent | Honest lender comparison with disclosure-first copy |
| Alternatives — TRANSWORLD SYSTEMS INC | `transworld systems alternative` | problem-aware intent | Honest lender comparison with disclosure-first copy |
| Alternatives — W&A Intermediate Co. | `w&a intermediate alternative` | problem-aware intent | Installment lender alternatives |
| Brand Intent — Billshappen | `bills happen`, `bills happen loans`, `billshappen`, `billshappen alternative`, `billshappen legit`, `billshappen loans`, `billshappen personal loan`, `billshappen.com` | brand/trademark intent | Radio-verified lender comparison; emphasize rates/terms disclosure, not impersonation |
| Brand Intent — Installment Loan | `fc holdco`, `onemain finance`, `clgf holdco 1`, `sofi technologies`, `cl`, `bread financial`, `ld`, `w&a intermediate` | brand/trademark intent | Side-by-side installment lender comparison with soft-pull pre-qual CTA |
| Brand Intent — Major Lenders | `jpmorgan chase &`, `jpmorgan chase & alternative`, `wells fargo &`, `wells fargo & alternative`, `capital one financial`, `capital one financial alternative`, `fifth third financial`, `fifth third financial alternative`, `u s bancorp`, `u s bancorp alternative`, `new york community bancorp`, `new york community bancorp alternative`, `citibank n a`, `citibank n a alternative`, `american express`, `american express alternative`, `bank of america national association`, `bank of america national association alternative`, `navy federal credit union`, `navy federal credit union alternative`, `td bank us holding`, `td bank us holding alternative`, `discover bank`, `discover bank alternative`, `truist financial`, `truist financial alternative`, `united services automobile association`, `united services automobile association alternative`, `bmo bank national association`, `bmo bank national association alternative`, `pnc bank n a`, `pnc bank n a alternative`, `synchrony financial`, `synchrony financial alternative`, `goldman sachs bank usa`, `goldman sachs bank usa alternative`, `citizens financial`, `citizens financial alternative`, `barclays bank delaware`, `barclays bank delaware alternative`, `huntington national bank the`, `huntington national bank the alternative` | brand/trademark intent | Major bank personal loan comparison; no logo impersonation |
| Debt / Tax Relief | `i c system`, `encore capital`, `portfolio recovery associates`, `resurgent capital services l p`, `transworld systems`, `national credit systems` | problem-aware intent | Debt consolidation / settlement vs new loan options |

## 4. Negative Keywords

| negative_keyword | reason |
|---|---|
| login | Existing customer account access |
| sign in | Navigational support traffic |
| customer service | Support intent not acquisition |
| phone number | Contact/support navigational |
| complaint | CFPB/reputation research not loan intent |
| complaints | Support/reputation traffic |
| reviews | Research without conversion intent |
| bbb | Reputation research |
| lawsuit | Legal research traffic |
| scam | Fraud research; high bounce |
| fraud | Fraud research traffic |
| career | Job seeker traffic |
| jobs | Recruitment traffic |
| hiring | Recruitment traffic |
| app download | Mobile app install intent |
| stock | Investor traffic (fintech brands) |
| investor | IR traffic |
| mortgage | Off-vertical unless running mortgage campaigns |
| refinance mortgage | Mortgage not personal loan vertical |
| auto loan | Auto finance off-vertical |
| car loan | Auto finance off-vertical |
| crypto | Crypto off-vertical |
| bitcoin | Crypto off-vertical |
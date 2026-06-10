# Keyword Curation — `config/loan_keywords.yaml`

Verified 2026-06-11 against the live `radio-worker` DB (1,346 transcripts,
52 distinct `ad_category` values, 232 detections, 134 canonical ads).

## File shape (gotcha)

`config/loan_keywords.yaml` is a **list of dicts**, not a flat string list:

```yaml
keywords:
  - phrase: tax relief
    confidence: 0.85
  - phrase: irs tax debt
    confidence: 0.95
  # ...35 total entries
```

Always extract the `phrase` field before iterating:

```python
kws = yaml.safe_load(open('/app/config/loan_keywords.yaml'))['keywords']
phrases = [k['phrase'] for k in kws]   # list[str]
```

The old `for kw in kws` pattern produces dicts, not strings, and silently
fails to match (TypeError on `kw.lower()` only fires on `.lower()`, not on
`in` — substring search "works" but always returns 0).

## Corpus reality (Texas talk radio, wbap + klif)

- 49% of corpus is local (roofing, mattress, traffic, news, health).
- 22% loan-adjacent: `tax_relief` (22), `debt_relief` (25), `business_funding` (43), `insurance` (27), `mortgage_refinance` (2), `life_insurance` (2).
- Many "expected" ad categories **do not appear at all**: `reverse_mortgage`, `home_equity`, `timeshare_exit`, `personal_loan`, `heloc`, `payday_loan`, `title_loan`, `cash_advance`, `same_day_funding`. Any keyword targeting these will be permanently DEAD until a finance-talk station is added.

## Verdict table from 2026-06-11 probe

| keyword | hits/121 | % | verdict |
|---|---|---|---|
| life insurance | 19 | 15.7% | ✅ broad but real |
| back taxes | 12 | 9.9% | ✅ |
| term life insurance | 12 | 9.9% | ✅ |
| stop collections | 10 | 8.3% | ✅ |
| unfiled tax returns | 9 | 7.4% | ✅ |
| timeshare exit | 6 | 5.0% | ✅ (despite no `timeshare_exit` ad_category — phrase still in raw transcript) |
| tax relief | 4 | 3.3% | ✅ |
| maintenance fees | 4 | 3.3% | ✅ (timeshare context) |
| debt relief | 2 | 1.7% | 🟡 rare |
| 26 others | 0 | 0% | ❌ DEAD (ban candidates — all have missing or empty target ad_category) |

## "Boring" 26 DEAD keywords (verified 0 hits even with `re.sub(r"[^a-z0-9 ]", " ", text)` normalization)

tax debt, tax debt relief, irs tax debt, irs debt, stop wage garnishment,
wage garnishment, garnish paycheck, seize bank accounts, debt consolidation,
business funding, business loan, working capital, merchant cash advance,
reverse mortgage, home equity loan, home equity line, second mortgage,
refinance your mortgage, cash-out refinance, final expense, burial insurance,
homeowners insurance, cancel timeshare, timeshare cancellation, exit your timeshare,
personal loan.

## Probe scripts (copy-paste)

### 1. Per-keyword hit count

```bash
docker exec radio-worker python -c "
import sqlite3, yaml
c = sqlite3.connect('/app/data/pipeline.db')
phrases = [k['phrase'] for k in yaml.safe_load(open('/app/config/loan_keywords.yaml'))['keywords']]
rows = c.execute('''SELECT t.text FROM transcripts t
                    JOIN detections d ON d.chunk_id = t.chunk_id''').fetchall()
hits = {p: 0 for p in phrases}
for (text,) in rows:
    tl = (text or '').lower()
    for p in phrases:
        if p.lower() in tl: hits[p] += 1
n = len(rows)
for p, h in sorted(hits.items(), key=lambda x: -x[1]):
    pct = h / n * 100 if n else 0
    flag = 'DEAD' if h == 0 else ('RARE' if pct < 1 else 'OK')
    print(f'  {p:30s} {h:5d}  {pct:6.2f}%  {flag}')
c.close()
"
```

### 2. Normalized probe (rules out ASR punctuation artifacts)

```bash
docker exec radio-worker python -c "
import sqlite3, re
c = sqlite3.connect('/app/data/pipeline.db')
def norm(t): return re.sub(r'[^a-z0-9 ]', ' ', (t or '').lower())
rows = c.execute('SELECT text FROM transcripts').fetchall()
# pick a known-true phrase, then test ASR-corrupted variants
true_phrase = 'unfiled tax returns'
n = 0
for (text,) in rows:
    if true_phrase in norm(text): n += 1
print(f'{true_phrase}: {n} normalized matches')
c.close()
"
```

If `unfiled tax returns` hits 9× both raw and normalized, ASR is fine and
the DEAD list is genuinely absent from the corpus (not an ASR artifact).

### 3. Per-ad_category sample transcript

```bash
docker exec radio-worker python -c "
import sqlite3, re
c = sqlite3.connect('/app/data/pipeline.db')
row = c.execute('''SELECT t.text FROM transcripts t
                   JOIN detections d ON d.chunk_id = t.chunk_id
                   WHERE d.ad_category = ? LIMIT 1''', ('tax_relief',)).fetchone()
print(re.sub(r'\s+', ' ', row[0])[:400])
c.close()
"
```

## Decision rule for ban-list review

Before banning a 0-hit keyword, present the operator with:

1. Hits/% over **all** transcripts (not just detection-joined)
2. Whether the **expected ad_category** appears in `detections` at all
3. One **sample transcript** from that ad_category (if it exists)
4. Verdict: BAN (genuinely absent), KEEP (target station not enabled), or
   PHRASE-FIX (ASR renders it differently)

Only edit `config/loan_keywords.yaml` after explicit operator confirm —
matches the "Ask before" rule in the parent skill.

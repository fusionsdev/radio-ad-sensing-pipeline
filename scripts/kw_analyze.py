"""One-off analysis: how many loan/funding-adjacent transcripts match loan_keywords.yaml?"""
import sqlite3, yaml, json, collections

c = sqlite3.connect('/app/data/pipeline.db')
kws = yaml.safe_load(open('/app/config/loan_keywords.yaml'))['keywords']
print(f"Loaded {len(kws)} keywords: {kws}\n")

rows = c.execute("""
  SELECT d.id, d.ad_category, d.company_name, d.offer_summary, d.key_claims, t.text
  FROM detections d JOIN transcripts t ON t.chunk_id = d.chunk_id
  WHERE d.ad_category IN ('business_funding','tax_relief','debt_relief')
  ORDER BY d.id DESC LIMIT 50
""").fetchall()

print(f"=== {len(rows)} loan-adjacent transcripts ===\n")
hits_by_kw = collections.Counter()
missed = []
for det_id, cat, co, offer, kc, text in rows:
    text = text or ''
    found_any = False
    for kw in kws:
        if kw.lower() in text.lower():
            hits_by_kw[kw] += 1
            found_any = True
    if not found_any:
        missed.append((det_id, cat, co, offer, kc, text[:300]))

print("Keyword hit counts (substring match in transcript):")
for k, v in hits_by_kw.most_common():
    print(f"  {k:28s} {v}")
print(f"\nMISSED detections: {len(missed)}\n")
for det_id, cat, co, offer, kc, ex in missed[:15]:
    print(f"[{cat}] {co or '(no co)'} | det_id={det_id}")
    print(f"  offer: {offer}")
    print(f"  kc:    {kc}")
    print(f"  excerpt: {ex!r}")
    print()
c.close()

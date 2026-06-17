"""Find any keyword_hits and false-positive risk: substring matches in non-ad transcripts."""
import sqlite3, yaml, collections, re

c = sqlite3.connect('/app/data/pipeline.db')
kws = yaml.safe_load(open('/app/config/loan_keywords.yaml'))['keywords']

# total transcripts and detection count
total_chunks_done = c.execute("SELECT COUNT(*) FROM chunks WHERE status='done'").fetchone()[0]
print(f"Total done chunks: {total_chunks_done}\n")

# Scan ALL transcripts to find how often each keyword fires (theoretical ceiling)
# and whether it lands in an ad-detected chunk or not.
rows = c.execute("""
  SELECT c.id, c.station_id, t.text,
         (SELECT d.id FROM detections d WHERE d.chunk_id=c.id LIMIT 1) AS det_id,
         (SELECT d.ad_category FROM detections d WHERE d.chunk_id=c.id LIMIT 1) AS cat
  FROM chunks c JOIN transcripts t ON t.chunk_id=c.id
  WHERE c.status='done'
""").fetchall()

kw_hits = collections.Counter()
kw_in_ad = collections.Counter()
kw_in_news = collections.Counter()  # no detection
sample_news_hits = collections.defaultdict(list)
sample_ad_hits = collections.defaultdict(list)

for cid, sid, text, det_id, cat in rows:
    text = (text or '').lower()
    for kw in kws:
        kwl = kw.lower()
        idx = text.find(kwl)
        if idx >= 0:
            kw_hits[kw] += 1
            if det_id:
                kw_in_ad[kw] += 1
                if len(sample_ad_hits[kw]) < 2:
                    ex = text[max(0,idx-60):idx+len(kwl)+60]
                    sample_ad_hits[kw].append((cid, cat, ex))
            else:
                kw_in_news[kw] += 1
                if len(sample_news_hits[kw]) < 2:
                    ex = text[max(0,idx-60):idx+len(kwl)+60]
                    sample_news_hits[kw].append((cid, ex))

print(f"=== Keyword frequency across {len(rows)} transcripts ===\n")
print(f"{'keyword':28s} {'hits':>5s} {'in_ad':>6s} {'in_news':>8s}  {'ad_yield':>9s}")
for kw in kws:
    h = kw_hits.get(kw, 0)
    ia = kw_in_ad.get(kw, 0)
    in_ = kw_in_news.get(kw, 0)
    yld = f"{(ia/h*100 if h else 0):.0f}%"
    print(f"{kw:28s} {h:5d} {ia:6d} {in_:8d}  {yld:>9s}")

print("\n=== Sample hits in NEWS context (potential false positives) ===")
for kw in kws:
    if sample_news_hits.get(kw):
        for cid, ex in sample_news_hits[kw]:
            print(f"  [{kw}] chunk {cid}")
            print(f"    ...{ex}...")

print("\n=== Sample hits in AD context (real positives) ===")
for kw in kws:
    if sample_ad_hits.get(kw):
        for cid, cat, ex in sample_ad_hits[kw]:
            print(f"  [{kw}] chunk {cid} cat={cat}")
            print(f"    ...{ex}...")

c.close()

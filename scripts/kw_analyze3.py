"""Frequency analysis: find loan/funding-related tokens in transcripts that ad-detection already flagged as loan-adjacent."""
import sqlite3, re, collections

c = sqlite3.connect('/app/data/pipeline.db')

rows = c.execute("""
  SELECT t.text, d.ad_category, d.company_name
  FROM detections d JOIN transcripts t ON t.chunk_id=d.chunk_id
  WHERE d.ad_category IN ('business_funding','tax_relief','debt_relief','insurance')
""").fetchall()

# tokenize + lowercase, count bigrams/trigrams that look ad-like
bigrams = collections.Counter()
trigrams = collections.Counter()
single = collections.Counter()
stop = set("the a an and or of in to for on with at from by is are was were be been being it this that these those you your we our they them i me my our not no as but if than then so do does did have has had can could would will shall may might just only very more most much some any all each every such also into over under between out up down off about because while when where how why who whom which what there here their its it's".split())

for text, cat, co in rows:
    words = re.findall(r"[a-z][a-z0-9'\-]+", (text or '').lower())
    words = [w for w in words if w not in stop and len(w) > 1]
    for w in words:
        single[w] += 1
    for a, b in zip(words, words[1:]):
        if a not in stop and b not in stop:
            bigrams[f"{a} {b}"] += 1
    for a, b, c2 in zip(words, words[1:], words[2:]):
        if a not in stop and c2 not in stop:
            trigrams[f"{a} {b} {c2}"] += 1

print("=== Top 25 unigrams in loan-adjacent transcripts ===")
for w, n in single.most_common(25):
    print(f"  {n:4d}  {w}")

print("\n=== Top 40 bigrams (potential candidate keywords) ===")
for w, n in bigrams.most_common(40):
    if n >= 2:
        print(f"  {n:4d}  {w}")

print("\n=== Top 30 trigrams ===")
for w, n in trigrams.most_common(30):
    if n >= 2:
        print(f"  {n:4d}  {w}")

c.close()

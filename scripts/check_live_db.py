"""Final extraction: dedupe against ALL sources and export fresh keyword candidates."""
import sqlite3
import re
import json
from collections import Counter
from datetime import datetime

DB = "/app/data/pipeline.db"

def q(sql):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(sql)
    rows = c.fetchall()
    conn.close()
    return rows

def norm(s):
    if not s:
        return ""
    return re.sub(r'[^a-z0-9]', '', s.lower().strip())

# ── 1. Load ALL existing keywords for comprehensive dedup ─────
existing_norms = set()

# From trademark_keyword_candidates
for r in q("SELECT DISTINCT normalized_keyword FROM trademark_keyword_candidates"):
    existing_norms.add(r[0].strip().lower())

# From trademark_entities
for r in q("SELECT normalized_name FROM trademark_entities"):
    existing_norms.add(r[0].strip().lower())

# From keyword_hits
for r in q("SELECT DISTINCT keyword FROM keyword_hits"):
    existing_norms.add(r[0].strip().lower())

# Hardcoded config-based keywords (known_keywords.yaml, known_entities.yaml, vertical_keywords.yaml)
config_keywords = [
    "personal loan", "installment loan", "payday loan", "cash loan", "cash advance",
    "bad credit loan", "emergency loan", "prequalify loan", "check your rate", "soft credit check",
    "carecredit", "care credit", "scratchpay", "scratch pay", "sofi", "lendingtree", "upstart",
    "upgrade", "rocket loans", "best egg", "avant", "lendingpoint", "onemain financial",
    "mariner finance", "klarna", "afterpay", "affirm", "sezzle", "sunbit", "cherry financing",
    "wisetack", "snap finance", "progressive leasing", "katapult", "consumer personal loan"
]
for kw in config_keywords:
    existing_norms.add(norm(kw))

print(f"Total existing keywords for dedup: {len(existing_norms)}", flush=True)

def is_new_candidate(name):
    """Check if a company name is truly new."""
    n = norm(name)
    if not n or len(n) < 3:
        return False
    for existing in existing_norms:
        if n == existing or n in existing or existing in n:
            return False
        # Check partial overlap - e.g., "viome" shouldn't match "viome.com"
        en = re.sub(r'[^a-z0-9]', '', existing)
        if len(en) > 3 and (n in en or en in n):
            return False
    return True

# ── 2. Extract from company_name field ─────────────────────────
print("\nExtracting from detections...", flush=True)
rows = q("""
    SELECT d.id, d.company_name, d.phone_number, d.website,
           d.offer_summary, d.key_claims,
           c.start_ts, st.name as station
    FROM detections d
    JOIN chunks c ON c.id = d.chunk_id
    JOIN stations st ON st.id = c.station_id
    WHERE d.is_ad = 1
    ORDER BY c.start_ts DESC
""")

companies = {}
phone_numbers = Counter()
websites = Counter()

for r in rows:
    did, company, phone, website, offer, claims, ts, station = r
    
    phone_n = norm(phone) if phone else None
    web_n = norm(website) if website else None
    
    if company:
        cn = company.strip()
        if cn not in companies:
            companies[cn] = {
                "count": 0, "phones": set(), "websites": set(),
                "stations": set(), "latest_ts": 0, "first_ts": float('inf'),
                "detection_ids": [], "offer_summaries": set(), "key_claims": set()
            }
        companies[cn]["count"] += 1
        if phone: companies[cn]["phones"].add(phone)
        if website: companies[cn]["websites"].add(website.lower())
        companies[cn]["stations"].add(station)
        companies[cn]["latest_ts"] = max(companies[cn]["latest_ts"], ts)
        companies[cn]["first_ts"] = min(companies[cn]["first_ts"], ts)
        companies[cn]["detection_ids"].append(did)
        if offer: companies[cn]["offer_summaries"].add(offer)
        if claims: companies[cn]["key_claims"].add(claims)
    
    if phone: phone_numbers[phone] += 1
    if website: websites[website.lower()] += 1

# Filter to NEW companies
new_companies = {k: v for k, v in sorted(companies.items(), key=lambda x: -x[1]["count"])
                 if is_new_candidate(k)}

# ── 3. Extract from transcript text (unnamed detections) ──────
print("Analyzing transcript text for unnamed detections...", flush=True)
rows_un = q("""
    SELECT d.id, t.text, c.start_ts, st.name as station
    FROM detections d
    JOIN transcripts t ON t.chunk_id = d.chunk_id
    JOIN chunks c ON c.id = d.chunk_id
    JOIN stations st ON st.id = c.station_id
    WHERE d.is_ad = 1 AND d.company_name IS NULL
    ORDER BY c.start_ts DESC
""")

# Simple heuristics to find brand/product names from transcript first lines
unnamed_keywords = []
for did, text, ts, station in rows_un:
    if not text:
        continue
    first_sentence = text.split('.')[0].strip()
    if first_sentence and len(first_sentence) > 10:
        unnamed_keywords.append({
            "detection_id": did,
            "first_sentence": first_sentence[:150],
            "ts": ts,
            "station": station,
            "text_snippet": text[:300]
        })

# ── 4. Output structured results ──────────────────────────────
output = {
    "generated_at": datetime.now().isoformat(),
    "db_freshness": {
        "detections": q("SELECT COUNT(*) FROM detections")[0][0],
        "transcripts": q("SELECT COUNT(*) FROM transcripts")[0][0],
        "chunks_done": q("SELECT COUNT(*) FROM chunks WHERE status='done'")[0][0],
        "latest_detection_ts": max((c["latest_ts"] for c in companies.values()), default=0),
        "latest_chunk_ts": q("SELECT MAX(start_ts) FROM chunks WHERE status='done'")[0][0],
    },
    "total_new_candidates": len(new_companies),
    "sources": {
        "from_company_name": len(new_companies),
        "from_transcript_only": len(unnamed_keywords),
    },
    "new_candidates": []
}

for rank, (name, info) in enumerate(new_companies.items(), 1):
    dt = datetime.fromtimestamp(info["latest_ts"])
    candidate = {
        "rank": rank,
        "company": name,
        "detection_count": info["count"],
        "phones": sorted(info["phones"]) if info["phones"] else [],
        "websites": sorted(info["websites"]) if info["websites"] else [],
        "stations": sorted(info["stations"]),
        "first_seen_ts": info["first_ts"],
        "latest_seen_ts": info["latest_ts"],
        "latest_seen": dt.isoformat(),
        "detection_ids": info["detection_ids"][:5],
        "offer_summaries": list(info["offer_summaries"])[:3] if info["offer_summaries"] else [],
        "suggested_keywords": [
            name.lower(),
            f"{name.lower()} reviews",
            f"{name.lower()} complaints",
            f"{name.lower()} bbb",
            f"{name.lower()} phone number",
        ]
    }
    if info["websites"]:
        # Add domain as keyword suggestion
        for site in info["websites"]:
            domain = re.sub(r'https?://(www\.)?', '', site).split('/')[0].split('.')[0]
            if domain and len(domain) > 2 and is_new_candidate(domain):
                candidate["suggested_keywords"].append(domain)
        # Deduplicate suggestions
        candidate["suggested_keywords"] = list(dict.fromkeys(candidate["suggested_keywords"]))
    
    output["new_candidates"].append(candidate)

# Print summary
print(f"\n{'='*80}")
print(f"FRESH KEYWORD CANDIDATES — {len(new_companies)} NEW companies found")
print(f"{'='*80}")

for c in output["new_candidates"][:40]:
    print(f"\n  #{c['rank']:3d} [{c['detection_count']:3d}x] {c['company']}")
    if c['phones']:
        print(f"         📞 {', '.join(c['phones'][:3])}")
    if c['websites']:
        print(f"         🌐 {', '.join(c['websites'][:3])}")
    print(f"         📡 {', '.join(c['stations'])}")
    print(f"         🕐 {c['latest_seen']}")

print(f"\n{'='*80}")
print(f"UNNAMED DETECTIONS (transcript analysis needed)")
print(f"{'='*80}")
for uk in unnamed_keywords[:20]:
    dt = datetime.fromtimestamp(uk["ts"])
    print(f"\n  #{uk['detection_id']} @ {dt} [{uk['station']}]")
    print(f"  → {uk['first_sentence']}")

# Export JSON
export_path = "/app/data/keyword_candidates_fresh.json"
with open(export_path, 'w') as f:
    json.dump(output, f, indent=2, default=str)
print(f"\n✅ Exported to {export_path}")

# Also print counts summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"  New company-name candidates: {len(new_companies)}")
print(f"  Unnamed detections to review: {len(unnamed_keywords)}")
print(f"  Top candidates by frequency:")
for c in output["new_candidates"][:10]:
    print(f"    {c['rank']:2d}. [{c['detection_count']:3d}x] {c['company']} — {', '.join(c['stations'][:3])}")

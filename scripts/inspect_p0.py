"""Load P0 candidates from scoring CSV + master JSONL for full context."""
import csv
import json

# Load scoring data
with open("exports/radio_financial_p0_p1_scoring.csv") as f:
    scored = list(csv.DictReader(f))

p0 = [r for r in scored if r["priority"] == "P0_test_now"]
print(f"P0 count: {len(p0)}")
for r in p0:
    print(f"  {r['company_name']:<40s} score={r['opportunity_score']:>4s} risk={r['risk_score']} {r['vertical']:<25s} dets={r['detections']:>3s}")

# Load master JSONL for full context (offer summaries, phones, stations list, etc.)
master = [json.loads(l) for l in open("data/radio_keyword_entity_master.jsonl")]

# Find matching master records
print("\n=== Master JSONL context ===")
for r in p0:
    name = r["company_name"]
    matches = [e for e in master if e["company_name"].lower() == name.lower()]
    if matches:
        e = matches[0]
        print(f"\n  {name}:")
        print(f"    phones: {e.get('phone', 'N/A')}")
        print(f"    sample_offer: {e.get('sample_offer', 'N/A')[:150] if e.get('sample_offer') else 'N/A'}")
        print(f"    stations: {e.get('stations', 'N/A')}")
        print(f"    first_seen: {e.get('first_seen', 'N/A')}")
        print(f"    last_seen: {e.get('last_seen', 'N/A')}")
        print(f"    notes: {e.get('notes', 'N/A')}")
    else:
        print(f"\n  {name}: NOT FOUND in master")

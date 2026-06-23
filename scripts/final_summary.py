"""Quick check of remaining unclassified and overall summary."""
import json

candidates = [json.loads(l) for l in open("data/radio_keyword_entity_master.jsonl")]

# Top unclassified
other = [e for e in candidates if e["vertical"] == "other"]
other.sort(key=lambda x: -x["detections"])
print("=== TOP 20 UNCLASSIFIED (other) ===")
for e in other[:20]:
    print(f"  [{e['detections']:3d}x] {e['company_name']:<30s} {e['website'] or ''}")

# Final summary
print(f"\n=== FINAL SUMMARY ===")
print(f"  Total: {len(candidates)}")
fin = [e for e in candidates if e["reporting_status"] == "report_now"]
sto = [e for e in candidates if e["reporting_status"] == "store_only"]
rev = [e for e in candidates if e["reporting_status"] == "manual_review"]
print(f"  report_now:   {len(fin)}")
print(f"  store_only:   {len(sto)}")
print(f"  manual_review: {len(rev)}")

# File sizes
import os
for f in ["data/radio_keyword_entity_master.jsonl", "exports/radio_keyword_entity_master.csv",
          "exports/radio_financial_opportunities_report.md",
          "exports/radio_future_vertical_archive_summary.md",
          "exports/radio_unknown_review_queue.csv"]:
    size = os.path.getsize(f)
    print(f"  {f}: {size/1024:.1f} KB")

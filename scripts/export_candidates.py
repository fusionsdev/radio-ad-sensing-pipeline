"""Generate CSV report of fresh keyword candidates."""
import json
import csv
import re
from datetime import datetime

# Read the JSON export
with open("data/keyword_candidates_fresh.json") as f:
    data = json.load(f)

# Write CSV
with open("exports/keyword_candidates_fresh.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Rank", "Company", "DetectionCount", "Phones", "Websites", "Stations", "LatestSeen", "SuggestedKeywords"])
    for c in data["new_candidates"]:
        w.writerow([
            c["rank"],
            c["company"],
            c["detection_count"],
            "; ".join(c["phones"][:3]),
            "; ".join(c["websites"][:3]),
            "; ".join(c["stations"]),
            c["latest_seen"],
            "; ".join(c["suggested_keywords"])
        ])

print(f"✅ CSV: exports/keyword_candidates_fresh.csv — {len(data['new_candidates'])} candidates")

# Write top-100 JSONL for quick triage
with open("exports/keyword_candidates_fresh_top100.jsonl", "w") as f:
    for c in data["new_candidates"][:100]:
        f.write(json.dumps(c) + "\n")

print(f"✅ JSONL: exports/keyword_candidates_fresh_top100.jsonl — top 100")

# Generate a simple text summary
with open("exports/fresh_keyword_findings.md", "w") as f:
    f.write("# Fresh Keyword Candidates — Live DB Extraction\n\n")
    f.write(f"**Generated**: {data['generated_at']}\n\n")
    f.write("## DB Freshness\n\n")
    f.write(f"| Metric | Value |\n")
    f.write(f"|---|---|\n")
    f.write(f"| Detections | {data['db_freshness']['detections']} |\n")
    f.write(f"| Transcripts | {data['db_freshness']['transcripts']} |\n")
    f.write(f"| Chunks (done) | {data['db_freshness']['chunks_done']} |\n")
    f.write(f"| Latest chunk | {datetime.fromtimestamp(data['db_freshness']['latest_chunk_ts'])} |\n\n")
    f.write(f"## Top 40 New Candidates\n\n")
    f.write(f"| # | Company | Count | Phones | Websites | Stations |\n")
    f.write(f"|---|---|---|---|---|---|\n")
    for c in data["new_candidates"][:40]:
        phones = ", ".join(c["phones"][:2])
        sites = ", ".join(c["websites"][:2])
        stas = ", ".join(list(c["stations"])[:4])
        f.write(f"| {c['rank']} | {c['company']} | {c['detection_count']} | {phones} | {sites} | {stas} |\n")
    
    f.write(f"\n## Total\n\n")
    f.write(f"- **{data['total_new_candidates']}** new company-name candidates found\n")
    f.write(f"- **{data['sources']['from_transcript_only']}** unnamed detections need transcript analysis\n")
    f.write(f"- Deduped against **483** existing keywords\n")

print(f"✅ MD: exports/fresh_keyword_findings.md")

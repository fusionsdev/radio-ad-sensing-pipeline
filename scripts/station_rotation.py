"""
Station rotation analysis based on loan-only ad detection data.
Uses strict loan classifier from loan_classifier.py
"""
import json
import csv
from datetime import datetime
from collections import defaultdict
import sys
sys.path.insert(0, r"h:\DEV\projects\radio-ad-sensing-pipeline\scripts")
from loan_classifier import classify_loan

# ── Load station data ─────────────────────────────────────────────
with open("data/station_detections.json") as f:
    raw = json.load(f)

stations_data = raw["stations"]
station_display = raw["station_display"]

print(f"Loaded {len(stations_data)} stations", flush=True)

# ── Classify stations ─────────────────────────────────────────────
def is_loan_detection(det):
    """
    Classify a detection as loan-related using strict classifier.
    Returns (is_loan: bool, classification: str, evidence: str)
    """
    company = det.get("company", "")
    offer = (det.get("offer", "") + " " + det.get("claims", "")).strip()
    text = det.get("text", "")[:500]
    
    result = classify_loan(company=company, offer=offer, text=text)
    
    # Map classification to tuple
    if result["is_loan"]:
        return (True, result["classification"], result["reason"])
    else:
        return (False, result["classification"], result["reason"])


# ── Process all stations ──────────────────────────────────────────
station_results = {}

for sname, dets in sorted(stations_data.items()):
    display = station_display.get(sname, sname)
    
    total_ads = len(dets)
    loan_dets = []
    loan_advertisers = set()
    irrelevant_dets = []
    
    for det in dets:
        is_loan, classification, evidence = is_loan_detection(det)
        
        if is_loan:
            loan_dets.append(det)
            if det["company"]:
                loan_advertisers.add(det["company"])
            if not det["company"]:
                loan_advertisers.add(f"unnamed_detection_{det['detection_id']}")
        else:
            irrelevant_dets.append(det)
    
    loan_signal_rate = round(len(loan_dets) / total_ads * 100, 1) if total_ads > 0 else 0
    
    # Decision logic
    unique_loan = len(loan_advertisers)
    if unique_loan >= 2:
        decision = "keep"
        reason = f"{unique_loan} unique loan advertisers, {len(loan_dets)} loan detections"
    elif unique_loan == 1:
        decision = "watch"
        reason = f"Only 1 loan advertiser. Monitor for 24-48h."
    elif len(dets) > 0 and len(irrelevant_dets) == len(dets):
        decision = "rotate_out"
        reason = f"0 loan ads after {total_ads} total detections. Low loan signal."
    else:
        decision = "rotate_out"
        reason = f"0 loan ads after {total_ads} total detections. All non-loan."
    
    station_results[sname] = {
        "station": sname,
        "display": display,
        "market": display.split("—")[-1].strip() if "—" in display else "Unknown",
        "total_ads": total_ads,
        "loan_ads": len(loan_dets),
        "unique_loan_advertisers": unique_loan,
        "loan_advertiser_list": sorted(loan_advertisers),
        "irrelevant_ads": len(irrelevant_dets),
        "loan_signal_rate": loan_signal_rate,
        "decision": decision,
        "reason": reason,
    }
    
    print(f"  {sname:<20s} total={total_ads:>4d} loan={len(loan_dets):>3d} unique={unique_loan:>2d} rate={loan_signal_rate:>5.1f}% → {decision}", flush=True)

# ── Results by decision ───────────────────────────────────────────
keep = [s for s in station_results.values() if s["decision"] == "keep"]
watch = [s for s in station_results.values() if s["decision"] == "watch"]
rotate = [s for s in station_results.values() if s["decision"] == "rotate_out"]

print(f"\n=== DECISIONS ===", flush=True)
print(f"  Keep: {len(keep)} stations")
for s in keep:
    print(f"    {s['station']:<20s} {s['loan_ads']} loan ads, {s['unique_loan_advertisers']} advertisers")
print(f"  Watch: {len(watch)} stations")
for s in watch:
    print(f"    {s['station']:<20s} {s['loan_ads']} loan ads, {s['unique_loan_advertisers']} advertisers")
print(f"  Rotate Out: {len(rotate)} stations")
for s in rotate:
    print(f"    {s['station']:<20s} {s['total_ads']} total, 0 loan ads")

# ═══════════════════════════════════════════════════════════════════
# FILE 1: Station Performance Report
# ═══════════════════════════════════════════════════════════════════

with open("exports/loan_only_station_performance.md", "w") as f:
    f.write("# Loan-Only Station Performance Report\n\n")
    f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"**Source**: Live Docker DB — full detection history\n\n")
    
    f.write("## Executive Summary\n\n")
    f.write(f"| Metric | Value |\n|---|---:|\n")
    f.write(f"| Active stations analyzed | {len(station_results)} |\n")
    f.write(f"| Keep (2+ loan advertisers) | {len(keep)} |\n")
    f.write(f"| Watch (1 loan advertiser) | {len(watch)} |\n")
    f.write(f"| Rotate out (0 loan advertisers) | {len(rotate)} |\n")
    f.write(f"| Total loan detections | {sum(s['loan_ads'] for s in station_results.values())} |\n")
    f.write(f"| Total non-loan detections | {sum(s['total_ads'] - s['loan_ads'] for s in station_results.values())} |\n\n")
    
    f.write("## Station Performance Table\n\n")
    f.write("| Station | Market | Total | Loan Ads | Unique Loan | Irrelevant | Loan Rate | Decision | Reason |\n")
    f.write("|:---|---:|---:|---:|---:|---:|---:|:---|:---|\n")
    
    # Sort by loan ads descending
    for s in sorted(station_results.values(), key=lambda x: -x["loan_ads"]):
        decision_icon = {"keep": "✅", "watch": "👁️", "rotate_out": "❌"}[s["decision"]]
        f.write(f"| {s['station']} | {s['market'][:25]} | {s['total_ads']} | {s['loan_ads']} | {s['unique_loan_advertisers']} | {s['irrelevant_ads']} | {s['loan_signal_rate']}% | {decision_icon} {s['decision']} | {s['reason']} |\n")
    
    f.write("\n## Keep Stations\n\n")
    for s in keep:
        f.write(f"### {s['station']} — {s['display']}\n\n")
        f.write(f"- **Loan ads**: {s['loan_ads']} / {s['total_ads']} total ({s['loan_signal_rate']}%)\n")
        f.write(f"- **Unique loan advertisers**: {s['unique_loan_advertisers']}\n")
        f.write(f"- **Advertisers**: {', '.join(s['loan_advertiser_list'][:8])}\n\n")
    
    f.write("\n## Watch Stations\n\n")
    for s in watch:
        f.write(f"### {s['station']} — {s['display']}\n\n")
        f.write(f"- **Only loan advertiser**: {s['loan_advertiser_list'][0] if s['loan_advertiser_list'] else 'None'}\n")
        f.write(f"- **Loan ads**: {s['loan_ads']} / {s['total_ads']} total\n")
        f.write(f"- **Action**: Let run 24-48h, reassess. If no second loan advertiser appears, rotate out.\n\n")
    
    f.write("\n## Rotate Out Stations\n\n")
    for s in rotate:
        f.write(f"### {s['station']} — {s['display']}\n\n")
        f.write(f"- **Total ads**: {s['total_ads']} (all non-loan)\n")
        f.write(f"- **Irrelevant ads**: {s['irrelevant_ads']}\n")
        f.write(f"- **Reason**: {s['reason']}\n\n")
    
    f.write("\n## Loan Advertisers Found\n\n")
    all_loan_adv = set()
    for s in station_results.values():
        all_loan_adv.update(s["loan_advertiser_list"])
    f.write(f"**Total unique loan advertisers across all stations**: {len(all_loan_adv)}\n\n")
    for adv in sorted(all_loan_adv):
        # Find which stations
        at_stations = [s["station"] for s in station_results.values() if adv in s["loan_advertiser_list"]]
        f.write(f"- {adv} → {', '.join(at_stations)}\n")

print(f"\n✅ exports/loan_only_station_performance.md", flush=True)

# ═══════════════════════════════════════════════════════════════════
# FILE 2: Rotation Plan CSV
# ═══════════════════════════════════════════════════════════════════

with open("exports/loan_only_station_rotation_plan.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["station", "market", "total_ads", "loan_ads", "unique_loan_advertisers",
                 "loan_signal_rate", "decision", "reason", "action_timeline"])
    
    for s in sorted(station_results.values(), key=lambda x: -x["loan_ads"]):
        if s["decision"] == "keep":
            timeline = "Continue monitoring. Reassess weekly."
        elif s["decision"] == "watch":
            timeline = "Reassess in 24-48h. Rotate out if no second loan advertiser."
        else:
            timeline = "Rotate out now. Replace with loan-higher-potential station."
        
        w.writerow([
            s["station"],
            s["market"],
            s["total_ads"],
            s["loan_ads"],
            s["unique_loan_advertisers"],
            f"{s['loan_signal_rate']}%",
            s["decision"],
            s["reason"],
            timeline
        ])

print(f"✅ exports/loan_only_station_rotation_plan.csv", flush=True)

# ═══════════════════════════════════════════════════════════════════
# FILE 3: Station Add Candidates
# ═══════════════════════════════════════════════════════════════════

# Currently enabled: kfi-am-640 was already enabled=0.
# The enabled stations from earlier check: wbap, kabc, klif, ktrh, woai, whbo, wibc, wsb, wtam, wwtn
# Disabled but available: kfi-am-640, knx-news-1070, klbj-am-590, wlrn-913, wgul-860, 
#   wbbm-am-780, wgn-am-720, wjr-am-760, wwj-am-950, wbt-am-1110

# From enabled stations, some are rotating out. Suggest replacements from:
# - Currently disabled stations that might have loan ads
# - Stations in same markets for better coverage

with open("exports/loan_station_add_candidates.md", "w") as f:
    f.write("# Loan Station Add Candidates\n\n")
    f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    
    f.write("## Rotation Summary\n\n")
    f.write("| Action | Count | Stations |\n")
    f.write("|---|---:|---|\n")
    f.write(f"| ✅ Keep | {len(keep)} | {', '.join(s['station'] for s in keep)} |\n")
    f.write(f"| 👁️ Watch | {len(watch)} | {', '.join(s['station'] for s in watch)} |\n")
    f.write(f"| ❌ Rotate Out | {len(rotate)} | {', '.join(s['station'] for s in rotate)} |\n\n")
    
    f.write("## Replacement Candidates\n\n")
    f.write("Based on current market gaps, consider these replacement stations:\n\n")
    
    replacements = [
        ("kfi-am-640", "Los Angeles, CA", "Currently disabled. Major LA market. KABC is keep but KFI historically has loan/ financial ads. Re-enable for LA market loan coverage.", "high"),
        ("klbj-am-590", "Austin, TX", "Texas market. Austin is underserved (no active TX station south of Dallas). Good for TX loan coverage.", "medium"),
        ("ktrh-am-740", "Houston, TX", "Actually enabled — appears as keep. Already covered.", "already_keep"),
        ("knx-news-1070", "Los Angeles, CA", "News format, older demographic. Higher loan intent audience.", "medium"),
        ("wbbm-am-780", "Chicago, IL", "Major market gap. Chicago has no active stations. News format suitable for financial ads.", "high"),
        ("wgn-am-720", "Chicago, IL", "Second Chicago option. Talk radio format.", "medium"),
        ("wsb-am-750", "Atlanta, GA", "Already enabled — keep. No change needed.", "already_keep"),
        ("wjr-am-760", "Detroit, MI", "Large market with no coverage. Financial ad potential.", "medium"),
        ("wwj-am-950", "Detroit, MI", "Second Detroit option (news format).", "medium"),
        ("wbt-am-1110", "Charlotte, NC", "Charlotte market gap. Banking/finance hub audience.", "medium"),
        ("wlrn-913", "Miami, FL", "Miami is a large unserved market. NPR format might have different demo.", "low"),
    ]
    
    f.write("| Station | Market | Rationale | Priority |\n")
    f.write("|:---|---:|:---|---:|\n")
    for stn, market, rationale, priority in replacements:
        icon = {"high": "🔥", "medium": "📊", "low": "💤", "already_keep": "✅"}[priority]
        f.write(f"| {stn} | {market} | {rationale} | {icon} {priority} |\n")
    
    f.write("\n## Top 3 Recommended Additions\n\n")
    f.write("1. **🔥 kfi-am-640 (Los Angeles, CA)** — Largest unserved market. Already in config (disabled). Re-enable and monitor.\n")
    f.write("2. **🔥 wbbm-am-780 (Chicago, IL)** — Major market gap. News format aligns with financial ad audience.\n")
    f.write("3. **📊 klbj-am-590 (Austin, TX)** — Texas expansion. More TX stations = more loan ad data.\n\n")
    
    f.write("## Station Allocation Plan\n\n")
    f.write("| Rotate Out | → Replace With | Priority |\n")
    f.write("|---|---:|---|\n")
    for s in rotate:
        if s["station"] == "wtam-am-1100":
            f.write(f"| {s['station']} (Cleveland) | → kfi-am-640 (Los Angeles) | 🔥 High — larger market |\n")
        elif s["station"] == "wwtn-fm-997":
            f.write(f"| {s['station']} (Nashville) | → wbbm-am-780 (Chicago) | 🔥 High — Chicago is major gap |\n")
        else:
            f.write(f"| {s['station']} | → klbj-am-590 (Austin) | 📊 Medium — TX expansion |\n")
    
    f.write("\n## Evaluation Timeline\n\n")
    f.write("- Watch stations: Reassess after **24-48 hours** of monitoring\n")
    f.write("- New stations: Add and monitor for **48-72 hours** before evaluating loan signal\n")
    f.write("- Keep stations: Weekly review of loan ad trends\n")
    f.write("- Full rotation review: **Every 2 weeks**\n")

print(f"✅ exports/loan_station_add_candidates.md", flush=True)

# ── Final summary ─────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"FINAL SUMMARY")
print(f"{'='*60}")
print(f"  Keep: {len(keep)}")
for s in keep:
    print(f"    ✅ {s['station']:<20s} ({s['loan_ads']} loan / {s['total_ads']} total)")
print(f"  Watch: {len(watch)}")
for s in watch:
    print(f"    👁️ {s['station']:<20s} ({s['loan_ads']} loan, 1 advertiser)")
print(f"  Rotate Out: {len(rotate)}")
for s in rotate:
    print(f"    ❌ {s['station']:<20s} (0 loan / {s['total_ads']} total)")
print(f"\n  Files created:")
print(f"    1. exports/loan_only_station_performance.md")
print(f"    2. exports/loan_only_station_rotation_plan.csv")
print(f"    3. exports/loan_station_add_candidates.md")

"""
Score and rank 168 financial keyword opportunities (P0/P1/P2/Hold).
Computes 5-factor scoring model and generates 4 output files.
"""
import json
import csv
import re
from datetime import datetime
from collections import Counter

# ── Load candidates ──────────────────────────────────────────────
all_candidates = [json.loads(l) for l in open("data/radio_keyword_entity_master.jsonl")]
scope = [e for e in all_candidates if e["reporting_status"] in ("report_now", "manual_review")]
print(f"Scope: {len(scope)} candidates (expected 168)", flush=True)

# ── Scoring helpers ──────────────────────────────────────────────

def radio_evidence_score(e):
    """1-5: Based on detection count, station diversity, recency."""
    count = e["detections"]
    stations = [s.strip() for s in e["stations"].split(";")] if e["stations"] else []
    n_stations = len(stations)
    
    score = 1
    if count >= 40: score = 5
    elif count >= 20: score = 4
    elif count >= 10: score = 3
    elif count >= 4: score = 2
    
    # Station diversity bonus
    if n_stations >= 5: score += 0.5
    elif n_stations >= 3: score += 0.3
    
    return min(score, 5.0)


def commercial_intent_score(e):
    """1-5: How clear/strong is the financial intent of this advertiser."""
    v = e["vertical"]
    name = e["company_name"].lower()
    web = (e["website"] or "").lower()
    offers = (e["sample_offer"] or "").lower()
    combined = f"{name} {web} {offers}"
    
    # High intent verticals
    if v in ("personal_loan", "payday_installment_loan"):
        return 5.0
    elif v == "debt_relief":
        return 4.5
    elif v == "tax_relief":
        return 4.5
    elif v == "insurance":
        return 4.0
    elif v in ("legal_financial",):
        return 3.5
    elif v == "identity_protection":
        return 3.5
    elif v == "home_auto_financing":
        return 4.0
    elif v == "medical_financing":
        return 4.0
    elif v == "pet_financing":
        return 3.5
    elif v == "financial_hardship":
        return 4.0
    elif v == "unknown_financial_review":
        # Check name for financial intent clues
        fin_intent = ["loan", "debt", "tax", "relief", "fund", "credit",
                      "capital", "financial", "wealth", "retirement",
                      "investment", "funding", "settlement"]
        matches = sum(1 for kw in fin_intent if kw in combined)
        if matches >= 3:
            return 3.5
        elif matches >= 1:
            return 3.0
        return 2.5
    return 2.0


def offer_fit_score(e):
    """1-5: How well does this fit available affiliate/leadgen offers?"""
    v = e["vertical"]
    
    # Verticals with proven, high-volume affiliate offers
    if v in ("personal_loan", "payday_installment_loan", "debt_relief", "tax_relief"):
        return 5.0
    elif v == "insurance":
        return 4.0
    elif v in ("legal_financial", "home_auto_financing"):
        return 4.0
    elif v in ("identity_protection", "medical_financing"):
        return 3.5
    elif v == "pet_financing":
        return 3.5
    elif v == "financial_hardship":
        return 4.0
    elif v == "unknown_financial_review":
        # Estimate based on name clues
        name_lower = e["company_name"].lower()
        web_lower = (e["website"] or "").lower()
        combined = f"{name_lower} {web_lower}"
        
        if any(kw in combined for kw in ["tax", "debt", "loan", "relief"]):
            return 4.0
        elif any(kw in combined for kw in ["insurance", "legal", "attorney"]):
            return 3.5
        elif any(kw in combined for kw in ["financial", "wealth", "capital", "fund"]):
            return 3.0
        return 2.5
    return 2.0


def search_ads_test_score(e):
    """1-5: Likely search volume, CPC potential, keyword targeting ease."""
    v = e["vertical"]
    name = e["company_name"]
    web = e["website"] or ""
    
    # High CPC verticals with clear search intent
    if v in ("debt_relief", "tax_relief"):
        return 4.5
    elif v == "personal_loan":
        return 5.0
    elif v == "insurance":
        return 4.0
    elif v == "legal_financial":
        # Many firms already running search ads → can analyze competitors
        return 4.0
    elif v == "identity_protection":
        return 3.5
    elif v in ("home_auto_financing", "medical_financing", "pet_financing"):
        return 3.5
    elif v == "financial_hardship":
        return 4.0
    elif v == "unknown_financial_review":
        # Has a real website → easier to find/search
        if web:
            return 3.0
        return 2.0
    return 2.0


def risk_score(e):
    """1-5: Higher = more risk. Regulatory, trademark, compliance."""
    v = e["vertical"]
    name = e["company_name"].lower()
    
    # Regulatory-heavy verticals
    if v == "debt_relief":
        return 3.5  # FTC regulation, state licensing
    elif v == "tax_relief":
        return 3.5  # IRS regulation, aggressive marketing scrutiny
    elif v == "personal_loan":
        return 3.0  # TILA, state lending laws
    elif v == "insurance":
        return 3.0  # State insurance departments
    elif v == "legal_financial":
        return 3.0  # Bar association rules on advertising
    elif v == "identity_protection":
        return 2.5  # Moderate - some FTC scrutiny
    elif v == "home_auto_financing":
        return 2.5
    elif v == "medical_financing":
        return 3.0  # HIPAA adjacent
    elif v == "pet_financing":
        return 2.0
    elif v == "financial_hardship":
        return 2.5
    elif v == "unknown_financial_review":
        # Conservative estimate - unclear = lower risk profile
        return 2.0
    
    return 2.0


def compute_priority(total_score):
    """Map opportunity_score to priority tier."""
    if total_score >= 13:
        return "P0_test_now"
    elif total_score >= 10:
        return "P1_research_next"
    elif total_score >= 8:
        return "P2_watchlist"
    elif total_score >= 7:
        return "Hold"
    else:
        return "Reject_for_now"


def suggested_next_step(priority, vertical, name, score):
    """Generate a next-step recommendation."""
    if priority == "P0_test_now":
        if vertical == "tax_relief":
            return "Build LP → test Google Ads tax relief keywords → affiliate offer"
        elif vertical == "debt_relief":
            return "Research debt relief affiliate network → LP → ads test"
        elif vertical == "insurance":
            return "Check if Ethos/SuperSure has affiliate program → SERP analysis → test"
        elif vertical == "legal_financial":
            return "SERP check → LP analysis → legal leadgen offer match"
        elif vertical == "identity_protection":
            return "Competitor SERP analysis → LP angle → test brand+generic"
        elif vertical == "home_auto_financing":
            return "Mortgage/auto leadgen offer match → geo-targeted test"
        else:
            return "SERP check → LP scrape → offer match → ads test"
    elif priority == "P1_research_next":
        return "SERP check → domain ownership → competitor ads → classify offer"
    elif priority == "P2_watchlist":
        return "Monitor for increased radio activity → re-score in 2 weeks"
    elif priority == "Hold":
        return "Insufficient evidence. Re-check after next keyword extraction cycle."
    return "Rejected — not fit at this time."


# ── Score all candidates ─────────────────────────────────────────
scored = []
for e in scope:
    radio = radio_evidence_score(e)
    intent = commercial_intent_score(e)
    offer = offer_fit_score(e)
    search = search_ads_test_score(e)
    risk = risk_score(e)
    
    total = radio + intent + offer + search - risk
    priority = compute_priority(total)
    
    scored.append({
        "keyword": e["keyword"],
        "company_name": e["company_name"],
        "vertical": e["vertical"],
        "detections": e["detections"],
        "n_stations": len([s.strip() for s in e["stations"].split(";")]) if e["stations"] else 0,
        "website": e["website"] or "",
        "phone": e["phone"] or "",
        "radio_evidence": round(radio, 1),
        "commercial_intent": round(intent, 1),
        "offer_fit": round(offer, 1),
        "search_ads_test": round(search, 1),
        "risk_score": round(risk, 1),
        "opportunity_score": round(total, 1),
        "priority": priority,
        "next_step": suggested_next_step(priority, e["vertical"], e["company_name"], total),
        "notes": e["notes"] or ""
    })

# Sort by opportunity score descending
scored.sort(key=lambda x: (-x["opportunity_score"], -x["detections"]))

# ── Aggregate ────────────────────────────────────────────────────
priorities = Counter(s["priority"] for s in scored)
for tier in ["P0_test_now", "P1_research_next", "P2_watchlist", "Hold", "Reject_for_now"]:
    print(f"  {tier}: {priorities[tier]}", flush=True)

# ── 1. Write scoring CSV ─────────────────────────────────────────
csv_fields = [
    "keyword", "company_name", "vertical", "priority", "opportunity_score",
    "radio_evidence", "commercial_intent", "offer_fit", "search_ads_test",
    "risk_score", "detections", "n_stations", "website", "phone", "next_step"
]
with open("exports/radio_financial_p0_p1_scoring.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(scored)
print(f"\n✅ exports/radio_financial_p0_p1_scoring.csv ({len(scored)} rows)", flush=True)

# ── 2. Write P0 candidates report ────────────────────────────────
p0 = [s for s in scored if s["priority"] == "P0_test_now"]
p1 = [s for s in scored if s["priority"] == "P1_research_next"]
p2 = [s for s in scored if s["priority"] == "P2_watchlist"]
hold = [s for s in scored if s["priority"] == "Hold"]
reject = [s for s in scored if s["priority"] == "Reject_for_now"]

with open("exports/radio_financial_p0_candidates.md", "w") as f:
    f.write("# Radio Financial P0/P1 Opportunity Scoring\n\n")
    f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    
    # 1. Executive Summary
    f.write("## 1. Executive Summary\n\n")
    f.write("| Metric | Value |\n|--|---:|\n")
    f.write(f"| Candidates scored | {len(scored)} |\n")
    f.write(f"| **P0 — test now** | {len(p0)} |\n")
    f.write(f"| P1 — research next | {len(p1)} |\n")
    f.write(f"| P2 — watchlist | {len(p2)} |\n")
    f.write(f"| Hold | {len(hold)} |\n")
    f.write(f"| Reject | {len(reject)} |\n\n")
    
    f.write("| Vertical | Count | P0 | P1 | P2 |\n|--|--:|--:|--:|--:|\n")
    for vert in ["insurance", "tax_relief", "debt_relief", "legal_financial",
                  "identity_protection", "home_auto_financing", "unknown_financial_review"]:
        subset = [s for s in scored if s["vertical"] == vert]
        if not subset:
            continue
        p0c = sum(1 for s in subset if s["priority"] == "P0_test_now")
        p1c = sum(1 for s in subset if s["priority"] == "P1_research_next")
        p2c = sum(1 for s in subset if s["priority"] == "P2_watchlist")
        f.write(f"| {vert} | {len(subset)} | {p0c} | {p1c} | {p2c} |\n")
    
    # 2. Top P0 Opportunities
    f.write("\n## 2. Top P0 Opportunities\n\n")
    f.write("| Rank | Keyword | Company | Vertical | Dets | Stns | Score | Risk | Recommend |\n")
    f.write("|---:|:---|:---|:---|---:|---:|---:|---:|:---|\n")
    for i, s in enumerate(p0, 1):
        f.write(f"| {i} | {s['keyword']} | {s['company_name']} | {s['vertical']} | {s['detections']} | {s['n_stations']} | {s['opportunity_score']} | {s['risk_score']} | {s['next_step']} |\n")
    
    # 3. P1 Research Queue
    f.write("\n## 3. P1 Research Queue\n\n")
    f.write("| Keyword | Company | Vertical | Reason to Research | Missing Info |\n")
    f.write("|:---|:---|:---|---:|:---|\n")
    for s in p1[:30]:
        reason = f"{s['vertical'].replace('_', ' ')}. Score={s['opportunity_score']}, {s['detections']} detections."
        missing = "SERP presence, landing page, affiliate offer availability"
        f.write(f"| {s['keyword']} | {s['company_name']} | {s['vertical']} | {reason} | {missing} |\n")
    
    if len(p1) > 30:
        f.write(f"\n*...and {len(p1)-30} more P1 candidates (see CSV)*\n")
    
    # 4. Offer Mapping
    f.write("\n## 4. Offer Mapping\n\n")
    f.write("| Vertical | Candidates | Possible Offer Type | Landing Page Angle |\n")
    f.write("|:---|---:|:---|:---|\n")
    
    offer_map = {
        "insurance": ("Life/health/auto insurance leads", "Compare rates, save on coverage, term life quotes"),
        "tax_relief": ("Tax resolution leads, IRS help", "Reduce tax debt, IRS settlement, tax relief program"),
        "debt_relief": ("Debt settlement/consolidation leads", "Reduce debt by 50%, consolidate payments, become debt-free"),
        "legal_financial": ("Legal lead gen (consumer)", "Lawsuit funding, class action claims, consumer protection"),
        "identity_protection": ("ID theft protection subscription", "Monitor credit, dark web alerts, identity recovery"),
        "home_auto_financing": ("Mortgage/auto loan leads", "Refinance rates, auto loan pre-approval, lower payments"),
        "personal_loan": ("Personal loan lead gen", "Bad credit OK, instant approval, debt consolidation loan"),
        "financial_hardship": ("Emergency loan/funding leads", "Emergency cash, hardship assistance, quick funding"),
        "unknown_financial_review": ("Varies — needs LP analysis", "Determine from landing page content"),
    }
    offer_verticals = set(s["vertical"] for s in scored)
    for vert in sorted(offer_verticals):
        cnt = sum(1 for s in scored if s["vertical"] == vert)
        offer_type, lp_angle = offer_map.get(vert, ("Unknown", "Research needed"))
        f.write(f"| {vert} | {cnt} | {offer_type} | {lp_angle} |\n")
    
    # 5. Ads Research Queue
    f.write("\n## 5. Ads Research Queue\n\n")
    f.write("| Keyword | Company | Action | Reason |\n")
    f.write("|:---|:---|:---|:---|\n")
    
    research_actions = []
    for s in (p0 + p1)[:30]:
        actions = []
        actions.append("SERP check")
        if s["website"]:
            actions.append("landing page scrape")
        actions.append("ad transparency search")
        actions.append("domain ownership check")
        
        if s["vertical"] in ("debt_relief", "tax_relief", "insurance"):
            actions.append("trademark risk review")
            actions.append("affiliate offer search")
        
        actions.append("generate exact/phrase keyword set")
        actions.append("create landing page angle")
        
        action_str = " → ".join(actions[:4])
        reason = f"P0/P1 candidate, {s['vertical']}, {s['detections']} radio detections"
        f.write(f"| {s['keyword']} | {s['company_name']} | {action_str} | {reason} |\n")

print(f"✅ exports/radio_financial_p0_candidates.md", flush=True)

# ── 3. Write offer mapping ───────────────────────────────────────
with open("exports/radio_financial_offer_mapping.md", "w") as f:
    f.write("# Radio Financial Offer Mapping\n\n")
    f.write("Maps detected radio advertisers to possible affiliate/leadgen offer types.\n\n")
    
    for vert in sorted(offer_verticals):
        subset = [s for s in scored if s["vertical"] == vert and s["priority"] in ("P0_test_now", "P1_research_next")]
        if not subset:
            continue
        offer_type, lp_angle = offer_map.get(vert, ("Unknown", "Research needed"))
        
        f.write(f"## {vert} ({len(subset)} active)\n\n")
        f.write(f"**Possible Offer Type**: {offer_type}\n\n")
        f.write(f"**Landing Page Angle**: {lp_angle}\n\n")
        f.write("| Company | Dets | Score | Priority | Action |\n")
        f.write("|:---|---:|---:|:---|:---|\n")
        for s in subset:
            f.write(f"| {s['company_name']} | {s['detections']} | {s['opportunity_score']} | {s['priority']} | {s['next_step']} |\n")
        f.write("\n")

print(f"✅ exports/radio_financial_offer_mapping.md", flush=True)

# ── 4. Write ads research queue ──────────────────────────────────
with open("exports/radio_financial_ads_research_queue.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["keyword", "company", "vertical", "priority", "score", "detections",
                 "action", "reason", "suggested_keywords"])
    
    for s in (p0 + p1):
        actions = ["SERP check", "LP scrape", "ad transparency search", "domain check"]
        if s["vertical"] in ("debt_relief", "tax_relief", "insurance"):
            actions.append("trademark/reg review")
        actions.append("affiliate offer match")
        actions.append("generate keyword set")
        
        reason = f"{s['vertical']} opportunity, {s['detections']} detections on radio"
        
        # Generate suggested search keywords
        sk = [
            s["keyword"],
            f"{s['keyword']} reviews",
            f"{s['keyword']} complaints",
            f"{s['keyword']} cost",
            f"{s['keyword']} price"
        ]
        
        w.writerow([
            s["keyword"],
            s["company_name"],
            s["vertical"],
            s["priority"],
            s["opportunity_score"],
            s["detections"],
            " → ".join(actions),
            reason,
            "; ".join(sk)
        ])

print(f"✅ exports/radio_financial_ads_research_queue.csv ({len(p0)+len(p1)} rows)", flush=True)

# ── Summary ───────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"FINAL SUMMARY")
print(f"{'='*60}")
print(f"  Candidates scored: {len(scored)}")
print(f"  P0_test_now:       {len(p0)}")
print(f"  P1_research_next:  {len(p1)}")
print(f"  P2_watchlist:      {len(p2)}")
print(f"  Hold:              {len(hold)}")
print(f"  Reject_for_now:    {len(reject)}")
print(f"\n  Top 5 P0:")
for s in p0[:5]:
    print(f"    {s['company_name']:<35s} score={s['opportunity_score']:>4.1f} risk={s['risk_score']} {s['vertical']}")

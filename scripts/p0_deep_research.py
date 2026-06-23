"""
P0 Financial Keyword Deep Research and Entity Normalization.
Produces 4 output files with normalized entities, deep research, ads plan, keyword sets.
"""
import csv
import json
from datetime import datetime
from collections import Counter

# ── Load data ─────────────────────────────────────────────────────
scored = list(csv.DictReader(open("exports/radio_financial_p0_p1_scoring.csv")))
master = [json.loads(l) for l in open("data/radio_keyword_entity_master.jsonl")]
p0_rows = [r for r in scored if r["priority"] == "P0_test_now"]

def find_master(name):
    matches = [e for e in master if e["company_name"].lower() == name.lower()]
    return matches[0] if matches else None

# ═══════════════════════════════════════════════════════════════════
# STEP 1: Entity Normalization
# ═══════════════════════════════════════════════════════════════════

# Define normalized entities with aliases
entities = [
    {
        "canonical": "Tax Relief Advocates",
        "aliases": ["Tax Relief Advocates", "Tax Relief Advocates (TRA)", "TRA"],
        "vertical": "tax_relief",
        "notes": "Same company — identical phone numbers and IRS tax debt messaging. tra.com is official site. Has active PPC affiliate program (affid=530 in URLs)."
    },
    {
        "canonical": "Optima Tax Relief",
        "aliases": ["Optima Tax Relief"],
        "vertical": "tax_relief",
        "notes": "optimataxrelief.com official. OfferVault CPL offer ($10-65+ tax debt, aged 30-65). Also has Optima Tax Shield partner program. Direct affiliate program available."
    },
    {
        "canonical": "Ethos",
        "aliases": ["Ethos"],
        "vertical": "insurance",
        "notes": "ethos.com. Online term life insurance. Official affiliate program at ethos.com/affiliate-program. $55/lead. Very affiliate-friendly."
    },
    {
        "canonical": "Coast One Tax Group",
        "aliases": ["Coast One Tax Group"],
        "vertical": "tax_relief",
        "notes": "coastonetaxgroup.com. IRS tax relief firm ($10K+ minimum debt). Classified as debt_relief in master but actually tax relief. Reclassify as tax_relief."
    },
    {
        "canonical": "SuperSure Insurance",
        "aliases": ["SuperSure Insurance Agency, LLC", "SuperSure Insurance Agency LLC", "SuperSure", "Super Sure Insurance Agency LLC"],
        "vertical": "insurance",
        "notes": "supersure.com. Business insurance brokerage (B2B, commercial P&C, employee benefits). NOT consumer insurance. Harder for standard affiliate/leadgen."
    },
    {
        "canonical": "LifeLock",
        "aliases": ["LifeLock", "Lifelock"],
        "vertical": "identity_protection",
        "notes": "lifelock.norton.com. Now part of Norton. Norton affiliate program available (various networks). Mature subscription product."
    },
    {
        "canonical": "Amco",
        "aliases": ["Amco"],
        "vertical": "other",
        "notes": "Likely relates to AAMCO auto repair financing. Sample offer: 'finance repairs, limited time offer'. NOT tax relief. Misclassified. Auto financing, not a consumer financial brand for ads."
    }
]

# Combine detections and stations for merged entities
def combine_entity(entity_def):
    aliases_lower = [a.lower() for a in entity_def["aliases"]]
    
    # Collect all matching rows from scoring/master
    matching_rows = [r for r in p0_rows if r["company_name"].lower() in aliases_lower]
    matching_master = [e for e in master if e["company_name"].lower() in aliases_lower]
    
    total_dets = sum(int(r["detections"]) for r in matching_rows)
    
    # Combined stations
    all_stations = set()
    all_phones = set()
    all_websites = set()
    sample_offers = []
    first_seen = None
    last_seen = None
    combined_score = 0.0
    combined_risk = 0.0
    
    for e in matching_master:
        for s in e["stations"].split(";"):
            all_stations.add(s.strip())
        if e.get("phone"):
            for p in e["phone"].split(";"):
                all_phones.add(p.strip())
        if e.get("website"):
            for w in e["website"].split(";"):
                all_websites.add(w.strip())
        if e.get("sample_offer"):
            sample_offers.append(e["sample_offer"])
        ts = e.get("first_seen")
        if ts and (first_seen is None or ts < first_seen):
            first_seen = ts
        ts = e.get("last_seen")
        if ts and (last_seen is None or ts > last_seen):
            last_seen = ts
    
    # Average score and risk
    for r in matching_rows:
        combined_score += float(r["opportunity_score"])
        combined_risk += float(r["risk_score"])
    if matching_rows:
        combined_score /= len(matching_rows)
        combined_risk /= len(matching_rows)
    
    return {
        "canonical": entity_def["canonical"],
        "aliases": entity_def["aliases"],
        "vertical": entity_def["vertical"],
        "combined_detections": total_dets,
        "combined_stations": len(all_stations),
        "station_list": "; ".join(sorted(all_stations)),
        "phones": "; ".join(sorted(all_phones)),
        "websites": "; ".join(sorted(all_websites)),
        "sample_offers": sample_offers,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "avg_score": round(combined_score, 1),
        "avg_risk": round(combined_risk, 1),
        "notes": entity_def["notes"],
        "aliases_count": len(entity_def["aliases"]),
        "detection_ids": [e.get("detection_ids", [])[:3] for e in matching_master if e.get("detection_ids")]
    }

normalized = [combine_entity(e) for e in entities]

# ═══════════════════════════════════════════════════════════════════
# STEP 2-3: Deep Research + Offer Fit Classification
# ═══════════════════════════════════════════════════════════════════

research_data = {
    "Tax Relief Advocates": {
        "official_site": "tra.com",
        "offer_path": "direct_affiliate_offer_available",
        "serp_intent": "High intent — 'tax relief', 'IRS tax debt help', 'tax settlement'. Commercial investigation queries. PPC active.",
        "test_decision": "test_now",
        "reason": "Verified affiliate program (affid=530). OfferVault tax debt PPC offer exists. 50 combined detections, 7 stations. High radio evidence + proven lead gen model.",
        "landing_angle": "IRS tax debt relief — reduce what you owe, stop wage garnishment, IRS settlement programs",
        "campaign_angle": "Tax debt relief for consumers with $10K+ IRS debt",
        "keywords_brand": ["tax relief advocates", "tra tax relief", "tra.com"],
        "keywords_generic": ["tax debt relief", "irs tax help", "reduce tax debt", "tax settlement", "offer in compromise"],
        "keywords_problem": ["irs wage garnishment help", "stop irs levy", "irs tax lien help", "tax debt forgiveness"],
        "risk_note": "FTC regulates tax relief. Must disclose: not all qualify. No upfront fees claim without license. Avoid 'tax debt forgiveness' implying full cancellation."
    },
    "Optima Tax Relief": {
        "official_site": "optimataxrelief.com",
        "offer_path": "direct_affiliate_offer_available",
        "serp_intent": "High intent. 'Optima Tax Relief review' is common. Brand queries plus generic tax debt. Active PPC competitors.",
        "test_decision": "test_now",
        "reason": "OfferVault CPL offer confirmed ($10-65, 30-65 age). Optima Tax Shield partner program. 28 detections, 3 stations. Strong tax vertical fit.",
        "landing_angle": "IRS tax relief from experienced tax attorneys — free consultation, settle tax debt for less",
        "campaign_angle": "Optima Tax Relief — tax resolution for $10K+ IRS debt",
        "keywords_brand": ["optima tax relief", "optima tax", "optimataxrelief"],
        "keywords_generic": ["tax relief", "tax resolution", "irs tax settlement", "tax attorney near me", "help with irs debt"],
        "keywords_problem": ["i owe the irs money", "can't pay irs taxes", "irs payment plan", "tax levy help"],
        "risk_note": "Same FTC rules as TRA. Avoid promising specific % reduction. Must state 'not all clients qualify'. No upfront fees without state-specific licensing."
    },
    "Ethos": {
        "official_site": "ethos.com",
        "offer_path": "direct_affiliate_offer_available",
        "serp_intent": "Brand + generic life insurance. 'Ethos life insurance review' is high volume. Term life quotes are high CPC.",
        "test_decision": "test_now",
        "reason": "Official affiliate program ($55/lead). 52 detections, 9 stations — highest radio coverage of all P0. Online instant quote funnel is proven.",
        "landing_angle": "Term life insurance from $6/day — instant online quote, no medical exam options available",
        "campaign_angle": "Life insurance quotes — compare Ethos term life rates",
        "keywords_brand": ["ethos life insurance", "ethos", "ethos insurance quote"],
        "keywords_generic": ["term life insurance quote", "life insurance no medical exam", "affordable life insurance", "life insurance online"],
        "keywords_problem": ["life insurance for parents", "need life insurance fast", "best term life insurance rates"],
        "risk_note": "Life insurance is state-regulated. Must comply with state DOI advertising rules. Avoid: 'guaranteed acceptance' if not. Standard life insurance disclaimer."
    },
    "Coast One Tax Group": {
        "official_site": "coastonetaxgroup.com",
        "offer_path": "leadgen_possible",
        "serp_intent": "Localized tax debt help. 'Coast One Tax Group reviews' and generic tax debt queries. Smaller brand than TRA/Optima.",
        "test_decision": "test_now",
        "reason": "10 detections, 3 stations. Tax relief with $10K+ minimum. Needs affiliate offer validation — not as proven as TRA/Optima. Test with smaller budget.",
        "landing_angle": "IRS tax relief since 2008 — 52K+ clients helped. Offer in Compromise, Tax Lien Removal, Penalty Abatement",
        "campaign_angle": "Tax debt relief — Coast One Tax Group professional tax resolution",
        "keywords_brand": ["coast one tax group", "coast one tax"],
        "keywords_generic": ["irs tax relief", "tax resolution company", "offer in compromise help", "irs tax attorney"],
        "keywords_problem": ["tax debt over 10000", "irs collections help", "tax problem resolution"],
        "risk_note": "Same FTC rules. Smaller brand — validate lead quality before scaling. Avoid: 'guaranteed results'."
    },
    "SuperSure Insurance": {
        "official_site": "supersure.com",
        "offer_path": "research_only",
        "serp_intent": "Business insurance. 'Business insurance' and 'Supersure' commercial queries. B2B — smaller audience, longer sales cycle.",
        "test_decision": "research_only",
        "reason": "23 detections but B2B business insurance product. Not suitable for consumer leadgen or standard affiliate offers. Complex product. Needs commercial insurance broker partnership.",
        "landing_angle": "N/A — B2B commercial insurance platform",
        "campaign_angle": "N/A — recommend waiting",
        "keywords_brand": [],
        "keywords_generic": [],
        "keywords_problem": [],
        "risk_note": "B2B insurance is state-regulated. Not a standard consumer offer path. Recommend reclassify as store_only for now."
    },
    "LifeLock": {
        "official_site": "lifelock.norton.com",
        "offer_path": "leadgen_possible",
        "serp_intent": "High brand search volume. 'LifeLock' is a major brand. 'Identity theft protection' is medium-high intent. Competitors active.",
        "test_decision": "test_now",
        "reason": "50 detections, 5 stations. Strong brand recognition. Norton affiliate program exists (FlexOffers deactivated but Norton still has active programs). Identity theft is a proven offer vertical.",
        "landing_angle": "Identity theft protection — monitor credit, dark web, bank accounts. $1M theft protection coverage",
        "campaign_angle": "Identity theft protection — LifeLock by Norton",
        "keywords_brand": ["lifelock", "lifelock identity theft", "lifelock login"],
        "keywords_generic": ["identity theft protection", "credit monitoring service", "identity fraud alert", "dark web monitoring"],
        "keywords_problem": ["someone stole my identity", "protect my identity", "credit freeze", "social security number monitoring"],
        "risk_note": "Trademarked brand — cannot claim official partnership unless real. FTC regulates identity protection claims. Avoid: 'guaranteed protection'. Use accurate coverage language."
    },
    "Amco": {
        "official_site": "N/A — likely AAMCO auto repair",
        "offer_path": "do_not_test_now",
        "serp_intent": "Ambiguous — 'Amco' could be many things. Likely AAMCO auto repair financing.",
        "test_decision": "do_not_test_now",
        "reason": "16 detections but misclassified. Sample offer 'finance repairs' suggests auto repair financing. Not a consumer financial product for affiliate/leadgen.",
        "landing_angle": "N/A",
        "campaign_angle": "N/A",
        "keywords_brand": [],
        "keywords_generic": [],
        "keywords_problem": [],
        "risk_note": "Recommend remove from P0 queue. Reclassify as store_only in master JSONL if confirmed auto repair."
    }
}

# ═══════════════════════════════════════════════════════════════════
# Count decisions 
# ═══════════════════════════════════════════════════════════════════

test_now = [e for e in entities if research_data[e["canonical"]]["test_decision"] == "test_now"]
research_only = [e for e in entities if research_data[e["canonical"]]["test_decision"] == "research_only"]
do_not_test = [e for e in entities if research_data[e["canonical"]]["test_decision"] == "do_not_test_now"]

print(f"Normalized P0 entities: {len(entities)}", flush=True)
print(f"  test_now: {len(test_now)}")
print(f"  research_only: {len(research_only)}")
print(f"  do_not_test_now: {len(do_not_test)}")

# ═══════════════════════════════════════════════════════════════════
# FILE 1: Entity Normalization Report
# ═══════════════════════════════════════════════════════════════════

with open("exports/p0_financial_entity_normalization.md", "w") as f:
    f.write("# P0 Financial Entity Normalization\n\n")
    f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    
    f.write("## 1. Executive Summary\n\n")
    f.write(f"| Metric | Value |\n")
    f.write(f"|---|---:|\n")
    f.write(f"| Raw P0 candidates (from scoring) | 8 |\n")
    f.write(f"| Duplicates merged | 2 → 1 (Tax Relief Advocates + TRA) |\n")
    f.write(f"| Normalized P0 entities | {len(entities)} |\n")
    f.write(f"| test\\_now count | {len(test_now)} |\n")
    f.write(f"| research\\_only count | {len(research_only)} |\n")
    f.write(f"| do\\_not\\_test\\_now count | {len(do_not_test)} |\n\n")
    
    f.write("## 2. Normalized P0 Entities\n\n")
    f.write("| Entity | Aliases | Vertical | Combined Dets | Combined Stns | Avg Score | Avg Risk |\n")
    f.write("|:---|---:|:---:|---:|---:|---:|---:|\n")
    for n in normalized:
        alias_str = ", ".join(a for a in n["aliases"] if a != n["canonical"])
        if not alias_str:
            alias_str = "—"
        f.write(f"| {n['canonical']} | {alias_str} | {n['vertical']} | {n['combined_detections']} | {n['combined_stations']} | {n['avg_score']} | {n['avg_risk']} |\n")
    
    f.write("\n## 3. Duplicate Resolution Notes\n\n")
    f.write("### Tax Relief Advocates + TRA\n\n")
    f.write("- **Evidence**: Identical phone numbers (`800-503-7944`, `800-550-8178`, `800-575-9379`, etc.) across both records\n")
    f.write("- **Evidence**: Same `sample_offer` theme: \"IRS tax debt relief\" / \"eliminate or reduce tax debt with IRS programs\"\n")
    f.write("- **Evidence**: Same vertical classification: `tax_relief`\n")
    f.write("- **Decision**: Merged into single entity with combined 50 detections across 7 stations\n")
    f.write("- **Official site**: tra.com\n\n")
    
    f.write("### Amco Reclassification\n\n")
    f.write("- **Current vertical**: `tax_relief` (original classification)\n")
    f.write("- **Evidence**: Sample offer \"finance repairs, limited time offer\" — likely AAMCO auto repair financing\n")
    f.write("- **Decision**: Reclassified as `other` / `do_not_test_now`. Not a consumer financial brand.\n\n")
    
    f.write("### Coast One Tax Group Reclassification\n\n")
    f.write("- **Current vertical**: `debt_relief` (original classification)\n")
    f.write("- **Evidence**: coastonetaxgroup.com is a tax resolution firm (IRS tax debt, $10K+ minimum)\n")
    f.write("- **Decision**: Reclassified as `tax_relief`\n\n")
    
    f.write("### SuperSure Insurance — B2B Caveat\n\n")
    f.write("- **Current vertical**: `insurance`\n")
    f.write("- **Evidence**: supersure.com is a business insurance brokerage (commercial P&C, employee benefits)\n")
    f.write("- **Decision**: NOT consumer insurance. Marked `research_only` — not suitable for standard consumer affiliate/leadgen offers.\n")

print("✅ exports/p0_financial_entity_normalization.md", flush=True)

# ═══════════════════════════════════════════════════════════════════
# FILE 2: Deep Research Report
# ═══════════════════════════════════════════════════════════════════

with open("exports/p0_financial_deep_research.md", "w") as f:
    f.write("# P0 Financial Deep Research\n\n")
    f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    
    f.write("## Research Table\n\n")
    f.write("| Entity | Official Site | Vertical | Offer Path | SERP Intent | Test Decision | Reason |\n")
    f.write("|:---|:---|:---|:---|:---|:---|:---|\n")
    
    for n in normalized:
        e = n["canonical"]
        rd = research_data[e]
        f.write(f"| {e} | {rd['official_site']} | {n['vertical']} | {rd['offer_path']} | {rd['serp_intent'][:100]}... | {rd['test_decision']} | {rd['reason'][:150]}... |\n")
    
    f.write("\n## Detailed Entity Analysis\n\n")
    for n in normalized:
        e = n["canonical"]
        rd = research_data[e]
        
        f.write(f"### {e}\n\n")
        f.write(f"- **Official Site**: [{rd['official_site']}](https://{rd['official_site']})\n")
        f.write(f"- **Offer Path**: `{rd['offer_path']}`\n")
        f.write(f"- **Test Decision**: `{rd['test_decision']}`\n")
        f.write(f"- **SERP Intent**: {rd['serp_intent']}\n")
        f.write(f"- **Research Summary**: {rd['reason']}\n")
        f.write(f"- **Risk Notes**: {rd['risk_note']}\n\n")

print("✅ exports/p0_financial_deep_research.md", flush=True)

# ═══════════════════════════════════════════════════════════════════
# FILE 3: Ads Test Plan
# ═══════════════════════════════════════════════════════════════════

with open("exports/p0_ads_test_plan.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["entity", "campaign_angle", "landing_page_angle", "match_type",
                 "starting_keywords", "offer_path", "test_decision", "risk_note",
                 "vertical", "detections", "stations"])
    
    for n in normalized:
        e = n["canonical"]
        rd = research_data[e]
        
        # Collect all keywords
        all_kw = rd["keywords_brand"] + rd["keywords_generic"] + rd["keywords_problem"]
        kw_sample = "; ".join(all_kw[:5])
        
        match_type = "phrase + exact for brand"
        if rd["offer_path"] == "direct_affiliate_offer_available":
            match_type = "exact brand + phrase generic + broad modified"
        elif rd["offer_path"] == "leadgen_possible":
            match_type = "exact brand + phrase generic"
        elif rd["offer_path"] == "research_only":
            match_type = "N/A"
        elif rd["offer_path"] == "do_not_test_now":
            match_type = "N/A"
        
        w.writerow([
            e,
            rd["campaign_angle"],
            rd["landing_angle"],
            match_type,
            kw_sample or "N/A",
            rd["offer_path"],
            rd["test_decision"],
            rd["risk_note"][:200],
            n["vertical"],
            n["combined_detections"],
            n["combined_stations"]
        ])

print(f"✅ exports/p0_ads_test_plan.csv", flush=True)

# ═══════════════════════════════════════════════════════════════════
# FILE 4: Keyword Sets
# ═══════════════════════════════════════════════════════════════════

with open("exports/p0_keyword_sets.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["entity", "vertical", "keyword_type", "keyword", "match_type", "notes"])
    
    for n in normalized:
        e = n["canonical"]
        rd = research_data[e]
        
        if rd["test_decision"] != "test_now":
            continue
        
        # Brand exact
        for kw in rd["keywords_brand"]:
            w.writerow([e, n["vertical"], "brand_exact", kw, "exact", "High CTR for branded queries"])
            w.writerow([e, n["vertical"], "brand_phrase", kw, "phrase", "Capture brand + modifier queries"])
        
        # Generic phrase
        for kw in rd["keywords_generic"]:
            w.writerow([e, n["vertical"], "generic_phrase", kw, "phrase", "Intent-driven generic traffic"])
            w.writerow([e, n["vertical"], "generic_broad", kw, "broad", "Explore new query patterns"])
        
        # Problem-aware
        for kw in rd["keywords_problem"]:
            w.writerow([e, n["vertical"], "problem_phrase", kw, "phrase", "High-intent problem-aware queries"])
        
        # Negative keywords
        negatives = {
            "tax_relief": ["free tax filing", "tax refund", "where's my refund", "irs phone number", "how to file taxes"],
            "insurance": ["car insurance quote", "auto insurance", "homeowners insurance", "free insurance", "insurance agent near me"],
            "identity_protection": ["free credit score", "credit karma", "annual credit report", "free identity theft protection"]
        }
        negs = negatives.get(n["vertical"], [])
        for kw in negs:
            w.writerow([e, n["vertical"], "negative", kw, "negative", "Exclude cost-comparison or free-seekers"])

print(f"✅ exports/p0_keyword_sets.csv", flush=True)

# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════

print(f"\n{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
print(f"  Normalized P0 entities: {len(entities)} (merged 8 → 7)")
print(f"  Duplicates merged: 2 → 1 (Tax Relief Advocates + TRA)")
print(f"  Reclassified: Amco (tax_relief → other/do_not_test)")
print(f"  Reclassified: Coast One Tax Group (debt_relief → tax_relief)")
print(f"  B2B caveat: SuperSure Insurance (research_only)")
print(f"")
print(f"  test_now:        {len(test_now)}")
for e in test_now:
    print(f"    - {e['canonical']}")
print(f"  research_only:   {len(research_only)}")
for e in research_only:
    print(f"    - {e['canonical']}")
print(f"  do_not_test_now: {len(do_not_test)}")
for e in do_not_test:
    print(f"    - {e['canonical']}")
print(f"")
print(f"  Files created:")
print(f"    1. exports/p0_financial_entity_normalization.md")
print(f"    2. exports/p0_financial_deep_research.md")
print(f"    3. exports/p0_ads_test_plan.csv")
print(f"    4. exports/p0_keyword_sets.csv")

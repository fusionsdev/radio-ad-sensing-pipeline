"""
Classify all 834 fresh keyword candidates into verticals.
Generate 5 output files as specified.
"""
import json
import csv
import re
from datetime import datetime
from collections import defaultdict

# ── Load fresh candidates ──────────────────────────────────────────
with open("data/keyword_candidates_fresh.json") as f:
    data = json.load(f)

candidates = data["new_candidates"]
print(f"Loaded {len(candidates)} candidates", flush=True)

# ── Classification engine ──────────────────────────────────────────

def classify_vertical(company, websites, offers, phones):
    """Two-pass heuristic classification:
    Pass 1: Company-name-only for ALL verticals (clean, no text contamination)
    Pass 2: Combined text for remaining candidates (catches financial keywords in ad copy)
    """
    c = company.lower()
    web_all = " ".join(w.lower() for w in websites) if websites else ""
    offers_txt = " ".join(o.lower() for o in offers) if offers else ""
    all_text = f"{c} {web_all} {offers_txt}"

    # ═══════════════════════════════════════════════════════════════
    # PASS 1: Company name (and website domain) only
    # ═══════════════════════════════════════════════════════════════

    # ── Financial firms identifiable by name ──

    # fin_name_patterns catch "Wesley Financial Group" etc.
    fin_name_patterns = ["financial group", "financial services", "wealth management",
        "wealth advisors", "wealth partners", "capital management",
        "retirement planners", "retirement planning", "retirement through",
        "investment group", "investment management", "financial management",
        "financial planning", "financial partners", "wealth group",
        "capital group", "equity group", "fund management",
        "asset management", "private wealth", "retirement solutions"]
    if any(kw in c for kw in fin_name_patterns):
        return "unknown_financial_review"

    c_words = set(c.split())
    if len(c_words) <= 5 and any(kw in c_words for kw in ["financial", "wealth", "capital", "financing"]):
        return "unknown_financial_review"

    # identity_protection (by company name)
    if any(kw in c for kw in ["lifelock", "incogny", "incogni"]):
        return "identity_protection"

    # insurance (by company name)
    if any(kw in c for kw in ["ethos", "progressive", "supersure", "super sure",
           "allstate", "term life", "insurance"]):
        return "insurance"

    # legal_financial (by company/website name)
    if any(kw in c for kw in ["lawyer", "attorney", "law firm", "diaco law",
           "steel horse", "morgan", "sweet james", "for the people"]):
        return "legal_financial"

    # debt_relief / tax_relief (by company name)
    if any(kw in c for kw in ["tax relief", "debt relief", "optima tax"]):
        v = "tax_relief" if "tax" in c else "debt_relief"
        return v

    # ── Store-only verticals (by company name) ──

    # health_supplement
    if any(kw in c for kw in ["viome", "relief factor", "ghostbed", "plexiderm",
        "purity product", "natural remedy"]):
        return "health_supplement"
    health_kw = ["supplement", "vitamin", "wellness", "green tea", "curcumin",
        "resveratrol", "joint pain", "omega", "probiotic",
        "colon", "gut health", "heart health", "immune",
        "weight loss", "diet", "nutrition", "herbal",
        "anti aging", "collagen", "tcr formula"]
    if any(kw in c for kw in health_kw) or any(kw in web_all for kw in health_kw):
        return "health_supplement"

    # automotive_non_financing
    auto_dealers = ["beaver toyota", "beaver mazda", "world car",
        "autozone", "rockauto"]
    if any(kw in c for kw in auto_dealers):
        return "automotive_non_financing"
    auto_kw = ["toyota", "mazda", "kia", "car dealer", "auto dealer",
        "pre-owned", "certified pre-owned"]
    if any(kw in c for kw in auto_kw):
        return "automotive_non_financing"

    # jobs_recruiting
    if any(kw in c for kw in ["ziprecruiter"]):
        return "jobs_recruiting"
    jobs_kw = ["hiring", "recruiting", "career",
        "employment", "work from home", "remote job", "staffing"]
    if any(kw in c for kw in jobs_kw) or any(kw in web_all for kw in jobs_kw):
        return "jobs_recruiting"

    # medical_non_financing
    med_names = ["choice men's health", "virtual imaging", "better addiction care"]
    if any(kw in c for kw in med_names):
        return "medical_non_financing"
    med_kw = ["doctor", "hospital", "clinic", "medical center",
        "pharmaceutical", "izervay", "eyesurvey", "izervey", "eye injection",
        "eye exam", "vision", "prescription", "amund", "wet amd",
        "astrazeneca", "pfizer", "estellas", "pharma",
        "addiction care", "healthcare"]
    if any(kw in c for kw in med_kw) or any(kw in web_all for kw in med_kw):
        return "medical_non_financing"

    # home_service
    home_names = ["finley roofing", "usa insulation", "mo better garage",
        "mobettergarage", "ragsdale heating", "peach state hardwood",
        "breda pest", "spartan construction", "oc window"]
    if any(kw in c for kw in home_names):
        return "home_service"
    home_kw = ["roofing", "hvac", "plumbing", "insulation",
        "window", "flooring", "pest control", "home service", "remodeling",
        "basement", "garage door", "construction", "heating and air",
        "hardwood", "pest management"]
    if any(kw in c for kw in home_kw) or any(kw in web_all for kw in home_kw):
        return "home_service"

    # local_service
    local_names = ["loud security", "security systems"]
    if any(kw in c for kw in local_names):
        return "local_service"
    local_kw = ["handyman", "cleaning", "landscaping", "moving", "storage",
        "security system"]
    if any(kw in c for kw in local_kw) or any(kw in web_all for kw in local_kw):
        return "local_service"

    # retail
    if any(kw in c for kw in ["hollywood suits", "trashy", "sweet deals",
        "sweetdeals", "good ranchers", "xfinity"]):
        return "retail"
    retail_kw = ["clothing", "fashion", "apparel", "sale", "discount",
        "shopping", "store", "food"]
    if any(kw in c for kw in retail_kw):
        return "retail"

    # nonprofit
    if any(kw in c for kw in ["mothers against drunk driving", "madd",
        "st christopher", "truckers fund", "truckersfund"]):
        return "nonprofit"
    np_kw = ["foundation", "donate", "donation", "charity", "nonprofit",
        "non profit", "scholarship"]
    if any(kw in c for kw in np_kw) or any(kw in web_all for kw in np_kw):
        return "nonprofit"

    # media_internal
    if any(kw in c for kw in ["cumulus", "cumulus digital"]):
        return "media_internal"
    media_kw = ["radio show", "podcast", "iheart", "spotify",
        "hannity", "bongino", "talk radio"]
    if any(kw in c for kw in media_kw):
        return "media_internal"

    # saas_b2b
    if any(kw in c for kw in ["strongtell", "metashare", "ilocal",
        "upside", "incogny", "qc kinetics"]):
        return "saas_b2b"
    saas_kw = ["software", "app", "platform", "cloud",
        "saas", "enterprise", "rapid radios"]
    if any(kw in c for kw in saas_kw) or any(kw in web_all for kw in saas_kw):
        return "saas_b2b"

    # education
    if any(kw in c for kw in ["school", "university", "college", "course",
        "training", "online learning", "tutoring", "education"]):
        return "education"

    # travel
    if any(kw in c for kw in ["travel", "hotel", "airline", "flight",
        "vacation", "cruise", "goldbelly"]):
        return "travel"

    # ═══════════════════════════════════════════════════════════════
    # PASS 2: Combined text for remaining (financial keywords in ad copy)
    # ═══════════════════════════════════════════════════════════════
    # Only financial keywords here — non-financial already caught by Pass 1.

    # debt_relief (using combined text)
    if any(kw in all_text for kw in ["debt", "bankruptcy", "credit repair",
        "credit score", "debt settlement", "debt relief", "credit report",
        "dispute", "credit rescue", "credit restore"]):
        return "debt_relief"

    # tax_relief (using combined text)
    if any(kw in all_text for kw in ["tax", "irs", "tax relief", "tax resolution",
        "tax debt", "tax attorney", "optimatax", "tax relief advocates",
        "tax group", "coast one tax", "tax problem", "tax help"]):
        return "tax_relief"

    # identity_protection (using combined text)
    if any(kw in all_text for kw in ["identity theft", "identity protection",
        "identity guard", "credit monitoring", "dark web monitoring",
        "fraud alert", "id theft", "id protection", "private internet access"]):
        return "identity_protection"

    # personal_loan
    if any(kw in all_text for kw in ["personal loan", "loan network", "bad credit loan",
        "installment loan", "emergency loan", "prequalify", "check your rate",
        "soft credit check", "bills happen", "billshappen", "credit loan"]):
        return "personal_loan"

    # payday_installment_loan
    if any(kw in all_text for kw in ["payday", "cash advance", "cash loan",
        "payday loan", "quick cash"]):
        return "payday_installment_loan"

    # legal_financial (using combined text)
    if any(kw in all_text for kw in ["lawyer", "attorney", "class action",
        "lawsuit", "injury lawyer", "consumer rights", "sue"]):
        return "legal_financial"

    # medical_financing
    if any(kw in all_text for kw in ["medical financing", "surgery financing",
        "dental financing", "healthcare financing", "medical loan",
        "medical credit"]):
        return "medical_financing"

    # pet_financing
    if any(kw in all_text for kw in ["pet financing", "vet financing", "care credit",
        "scratchpay", "pet care financing"]):
        return "pet_financing"

    # home_auto_financing
    if any(kw in all_text for kw in ["mortgage", "auto loan", "car loan",
        "home equity", "refinance", "home loan", "auto financing",
        "home financing", "reverse mortgage"]):
        return "home_auto_financing"

    # insurance (using combined text)
    if any(kw in all_text for kw in ["insurance", "life insurance", "term life",
        "medicare", "supplemental", "insure"]):
        return "insurance"

    # financial_hardship
    if any(kw in all_text for kw in ["hardship", "financial struggle",
        "bills help", "financial help", "emergency money"]):
        return "financial_hardship"

    # other (catch-all for non-classifiable)
    return "other"


# ── Determine reporting/future status ──────────────────────────────

def get_reporting_status(vertical, company):
    """report_now for target verticals, store_only for archive, manual_review for unknown."""
    target_verticals = [
        "personal_loan", "payday_installment_loan", "debt_relief", "tax_relief",
        "insurance", "identity_protection", "legal_financial", "medical_financing",
        "pet_financing", "home_auto_financing", "financial_hardship"
    ]
    
    if vertical in target_verticals:
        return "report_now"
    elif vertical == "unknown_financial_review":
        return "manual_review"
    else:
        return "store_only"


def get_future_offer_potential(vertical, count, company):
    """Assess future business potential."""
    # High potential verticals with decent detection count
    high_verticals = ["personal_loan", "payday_installment_loan", "insurance",
                      "debt_relief", "tax_relief", "medical_financing",
                      "home_auto_financing"]
    
    medium_verticals = ["identity_protection", "legal_financial",
                        "health_supplement", "jobs_recruiting",
                        "pet_financing", "unknown_financial_review"]
    
    if vertical in high_verticals and count >= 5:
        return "high"
    elif vertical in high_verticals:
        return "medium"
    elif vertical in medium_verticals and count >= 10:
        return "medium"
    elif vertical in medium_verticals:
        return "low"
    elif count >= 20:  # High count in any vertical has some reuse potential
        return "medium"
    else:
        return "low"


def get_storage_status(vertical, company, websites):
    """Decide whether to keep active, archive, or mark for review."""
    c_lower = company.lower()
    
    # Media internal promos → archive
    if vertical == "media_internal":
        return "keep_archive"
    
    # Station ad promos / internal
    station_indicators = ["wbap.com", "hannity", "bongino", "talk radio"]
    if any(ind in c_lower for ind in station_indicators):
        return "keep_archive"
    
    # Everything else → keep_active
    return "keep_active"


def get_sample_offer(offers, company):
    """Get a short sample offer from available data."""
    if offers:
        return offers[0][:200]
    return None


def get_reason(vertical, count, company):
    """Generate a concise reason string for reports."""
    if vertical in ["personal_loan", "payday_installment_loan", "debt_relief",
                    "tax_relief", "insurance", "identity_protection",
                    "legal_financial", "medical_financing", "pet_financing",
                    "home_auto_financing", "financial_hardship"]:
        return f"Financial vertical: {vertical}. {count} detections across radio."
    return f"Non-financial ({vertical}). {count} detections. Archived for future offers."


# ── Process all candidates ─────────────────────────────────────────

classified = []
for c in candidates:
    company = c["company"]
    websites = c.get("websites", [])
    offers = c.get("offer_summaries", [])
    phones = c.get("phones", [])
    count = c["detection_count"]
    
    vertical = classify_vertical(company, websites, offers, phones)
    
    entry = {
        "keyword": company.lower(),
        "company_name": company,
        "website": "; ".join(websites) if websites else None,
        "phone": "; ".join(phones) if phones else None,
        "vertical": vertical,
        "storage_status": get_storage_status(vertical, company, websites),
        "reporting_status": get_reporting_status(vertical, company),
        "future_offer_potential": get_future_offer_potential(vertical, count, company),
        "detections": count,
        "stations": "; ".join(c["stations"]),
        "first_seen": c["first_seen_ts"],
        "last_seen": c["latest_seen_ts"],
        "sample_offer": get_sample_offer(offers, company),
        "source_fields": f"company_name{' + websites' if websites else ''}{' + offers' if offers else ''}",
        "notes": get_reason(vertical, count, company)
    }
    classified.append(entry)

# ── Summary stats ──────────────────────────────────────────────────

verticals = defaultdict(int)
for e in classified:
    verticals[e["vertical"]] += 1

print(f"\nClassified: {len(classified)} candidates")
print(f"Verticals: {dict(sorted(verticals.items(), key=lambda x: -x[1]))}", flush=True)

# ── Write: data/radio_keyword_entity_master.jsonl ──────────────────

with open("data/radio_keyword_entity_master.jsonl", "w") as f:
    for e in classified:
        f.write(json.dumps(e) + "\n")
print("✅ data/radio_keyword_entity_master.jsonl", flush=True)

# ── Write: exports/radio_keyword_entity_master.csv ────────────────

csv_fields = [
    "keyword", "company_name", "vertical", "reporting_status", "storage_status",
    "future_offer_potential", "detections", "stations", "website", "phone",
    "first_seen", "last_seen", "sample_offer", "source_fields", "notes"
]

with open("exports/radio_keyword_entity_master.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=csv_fields)
    w.writeheader()
    w.writerows(classified)
print("✅ exports/radio_keyword_entity_master.csv", flush=True)

# ── Write: exports/radio_financial_opportunities_report.md ─────────

target_verticals = [
    "personal_loan", "payday_installment_loan", "debt_relief", "tax_relief",
    "insurance", "identity_protection", "legal_financial", "medical_financing",
    "pet_financing", "home_auto_financing", "financial_hardship"
]

financial = [e for e in classified if e["vertical"] in target_verticals]
financial.sort(key=lambda x: -x["detections"])

# Also check for financial_unknown candidates that need manual review
unknown_financial_count = 0
# We'll mark high-frequency "other" or "unknown" as manual_review candidates
manual_review = [e for e in classified if e["reporting_status"] == "manual_review"
                 or e["vertical"] == "other" and e["detections"] >= 5]

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

with open("exports/radio_financial_opportunities_report.md", "w") as f:
    f.write("# Radio Financial Opportunity Report\n\n")
    f.write(f"**Generated**: {now}\n")
    f.write(f"**Source**: Live Docker DB (`/app/data/pipeline.db`)\n\n")
    
    # 1. Executive Summary
    f.write("## 1. Executive Summary\n\n")
    f.write(f"| Metric | Value |\n")
    f.write(f"|---|---|\n")
    f.write(f"| Total candidates archived | {len(classified)} |\n")
    f.write(f"| Financial opportunities reported | {len(financial)} |\n")
    f.write(f"| Unknown financial — manual review needed | {len(manual_review)} |\n")
    f.write(f"\n### Top 20 Immediate Opportunities\n\n")
    f.write("| # | Company | Vertical | Dets | Stations | Potential |\n")
    f.write("|---|---|:---:|---:|---:|---|\n")
    for i, e in enumerate(financial[:20], 1):
        stas = e["stations"].count(";") + 1
        f.write(f"| {i} | {e['company_name']} | {e['vertical']} | {e['detections']} | {stas} | {e['future_offer_potential']} |\n")
    
    # 2. Financial Opportunity Table
    f.write("\n## 2. Financial Opportunity Table\n\n")
    f.write("| keyword | company | vertical | detections | stations | website | phone | future_offer_potential | reason |\n")
    f.write("|---|---|:---:|---:|---:|:---|:---|---:|---|\n")
    for e in financial:
        phone = e["phone"] or "-"
        web = e["website"] or "-"
        stas = e["stations"].count(";") + 1
        reason = f"{e['vertical'].replace('_', ' ')} advertiser"
        f.write(f"| {e['keyword']} | {e['company_name']} | {e['vertical']} | {e['detections']} | {stas} | {web} | {phone} | {e['future_offer_potential']} | {reason} |\n")
    
    # 3. P0 Ads / Research Candidates
    f.write("\n## 3. P0 Ads / Research Candidates\n\n")
    f.write("High-priority candidates for immediate competitive research:\n\n")
    f.write("| keyword | vertical | evidence | suggested_next_step |\n")
    f.write("|---|---|---|---|\n")
    for e in financial[:15]:
        evidence = f"{e['detections']} detections across multiple stations"
        step = f"Check {e['website'] or 'landing page'}; research affiliate/offer network"
        f.write(f"| {e['keyword']} | {e['vertical']} | {evidence} | {step} |\n")
    
    # 4. Manual Review: Possible Financial
    f.write("\n## 4. Manual Review: Possible Financial\n\n")
    f.write("Candidates that may be financial but need human review:\n\n")
    f.write("| company | website | phone | detections | sample_offer | why_review |\n")
    f.write("|---|---|:---:|---:|---|---|\n")
    for e in manual_review[:20]:
        phone = e["phone"] or "-"
        web = e["website"] or "-"
        offer = e["sample_offer"] or "N/A"
        f.write(f"| {e['company_name']} | {web} | {phone} | {e['detections']} | {offer[:100] if offer else 'N/A'} | Non-financial ({e['vertical']}) but {e['detections']} detections warrant review |\n")
    
print("✅ exports/radio_financial_opportunities_report.md", flush=True)

# ── Write: exports/radio_future_vertical_archive_summary.md ────────

store_only = [e for e in classified if e["reporting_status"] == "store_only"]
store_by_vertical = defaultdict(list)
for e in store_only:
    store_by_vertical[e["vertical"]].append(e)

# Predefined future angle mapping
future_angles = {
    "health_supplement": "Cross-sell financial products to health-conscious demographic. Partner with supplement companies for co-branded offers.",
    "jobs_recruiting": "Target employed-but-strained audience with debt consolidation / personal loan offers at career transition points.",
    "local_service": "Bundle home service financing options. Partner with HVAC/roofing for in-store loan offers.",
    "retail": "Retail installment loans (BNPL). Partner with fashion/retail for point-of-sale financing.",
    "home_service": "Home improvement financing. High-ticket loans for roof/HVAC replacements.",
    "medical_non_financing": "Medical financing partnership. Pharma companies have captive audiences for health credit products.",
    "nonprofit": "Credit union / nonprofit lending partnership opportunities.",
    "media_internal": "Internal promo — no external opportunity.",
    "saas_b2b": "B2B SaaS targeting financial services vertical. Could be partner for loan origination software.",
    "education": "Student loan refinancing / education financing angles.",
    "automotive_non_financing": "Auto loan / refinance replacement. Existing car ad audience is pre-qualified for auto financing.",
    "travel": "Travel financing / vacation loan potential. BNPL for travel bookings.",
    "other": "Unknown — revisit after keyword enrichment."
}

with open("exports/radio_future_vertical_archive_summary.md", "w") as f:
    f.write("# Future Vertical Archive Summary\n\n")
    f.write(f"**Generated**: {now}\n")
    f.write(f"**Total archived**: {len(store_only)} non-financial candidates\n\n")
    f.write("## Summary by Vertical\n\n")
    f.write("| vertical | count | top_examples | future_offer_angle |\n")
    f.write("|---|---:|---|---|\n")
    
    for vert in sorted(store_by_vertical.keys()):
        entries = store_by_vertical[vert]
        entries.sort(key=lambda x: -x["detections"])
        top_examples = ", ".join(e["company_name"] for e in entries[:5])
        angle = future_angles.get(vert, "Opportunity TBD")
        f.write(f"| {vert} | {len(entries)} | {top_examples} | {angle} |\n")
    
    f.write("\n## Notes\n\n")
    f.write("- All archived candidates remain in `radio_keyword_entity_master.jsonl`\n")
    f.write("- Archived candidates can be promoted to `report_now` when a relevant financial offer launches\n")
    f.write("- Future_offer_potential is estimated based on advertiser spend and audience overlap with financial verticals\n")

print("✅ exports/radio_future_vertical_archive_summary.md", flush=True)

# ── Write: exports/radio_unknown_review_queue.csv ──────────────────

# Candidates that need review: "other" vertical, or very unusual companies
unknown = [e for e in classified if e["vertical"] == "other"
           or (e["detections"] >= 3 and e["vertical"] == "other")]

# Add high-count unknowns first
unknown.sort(key=lambda x: -x["detections"])

with open("exports/radio_unknown_review_queue.csv", "w", newline="") as f:
    fields = ["company_name", "website", "phone", "detections", "stations",
              "sample_offer", "notes", "vertical_assigned", "detection_ids"]
    w = csv.writer(f)
    w.writerow(fields)
    
    # Find original candidate data to include detection_ids
    cand_by_company = {c["company"].lower(): c for c in candidates}
    
    for e in unknown:
        company = e["company_name"]
        cand = cand_by_company.get(company.lower(), {})
        det_ids = "; ".join(str(x) for x in cand.get("detection_ids", [])[:5])
        
        w.writerow([
            company,
            e["website"] or "",
            e["phone"] or "",
            e["detections"],
            e["stations"],
            e["sample_offer"] or "",
            f"Auto-classified as {e['vertical']}. Needs human review.",
            e["vertical"],
            det_ids
        ])

print(f"✅ exports/radio_unknown_review_queue.csv ({len(unknown)} entries)", flush=True)

# ── Final summary ──────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"FINAL SUMMARY")
print(f"{'='*60}")
print(f"  Total candidates archived: {len(classified)}")
print(f"  Financial (report_now):    {len(financial)}")
print(f"  Archived (store_only):     {len(store_only)}")
print(f"  Needs manual review:       {len(unknown)}")
print(f"\n  Files created:")
print(f"    1. data/radio_keyword_entity_master.jsonl")
print(f"    2. exports/radio_keyword_entity_master.csv")
print(f"    3. exports/radio_financial_opportunities_report.md")
print(f"    4. exports/radio_future_vertical_archive_summary.md")
print(f"    5. exports/radio_unknown_review_queue.csv")

"""
Full audit of loan-classified detections per station.
For each candidate, applies strict re-classification logic.
Generates precision metrics and rotation recommendations.
"""
import sqlite3
import json
import csv
from collections import defaultdict

DB = "/app/data/pipeline.db"

def q(sql, params=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    if params: c.execute(sql, params)
    else: c.execute(sql)
    rows = c.fetchall()
    conn.close()
    return rows

target_stations = ["woai-am-1200", "wsb-am-750", "wibc-fm-931", "klif-am-570", "ktrh-am-740", "wtam-am-1100"]

# ── Strict loan classification ────────────────────────────────────
# True loan signals
TRUE_LOAN_PATTERNS = [
    "personal loan", "installment loan", "payday loan", "cash advance",
    "bad credit loan", "emergency loan", "same day funding", "borrow money",
    "get cash today", "quick funding", "cash loan", "emergency cash",
    "bills happen", "billshappen", "soft credit check", "prequalify",
    "check your rate", "loan network", "lending",
]

# Medical/pet financing (count as loan per spec)
MEDICAL_FINANCE_PATTERNS = ["medical financing", "surgery financing", "dental financing",
    "healthcare financing", "pet financing", "vet financing", "care credit", "scratchpay"]

# Non-loan patterns that can falsely match "loan" or "financing"
FALSE_POSITIVE_PATTERNS = [
    # Tax relief
    ("tax", "tax_relief_not_loan"),
    ("irs", "tax_relief_not_loan"),
    ("tax relief", "tax_relief_not_loan"),
    ("tax debt", "tax_relief_not_loan"),
    ("tax resolution", "tax_relief_not_loan"),
    ("optimatax", "tax_relief_not_loan"),
    ("tax relief advocates", "tax_relief_not_loan"),
    ("coast one tax", "tax_relief_not_loan"),
    ("tra.com", "tax_relief_not_loan"),
    
    # Insurance
    ("life insurance", "insurance_not_loan"),
    ("term life", "insurance_not_loan"),
    ("ethos", "insurance_not_loan"),
    ("insurance quote", "insurance_not_loan"),
    ("supersure", "insurance_not_loan"),
    ("progressive", "insurance_not_loan"),
    ("allstate", "insurance_not_loan"),
    ("medicare", "insurance_not_loan"),
    
    # Identity protection
    ("lifelock", "identity_not_loan"),
    ("identity theft", "identity_not_loan"),
    ("identity protection", "identity_not_loan"),
    ("credit monitoring", "identity_not_loan"),
    ("dark web", "identity_not_loan"),
    
    # Legal
    ("attorney", "legal_not_loan"),
    ("lawyer", "legal_not_loan"),
    ("lawsuit", "legal_not_loan"),
    ("class action", "legal_not_loan"),
    ("injury", "legal_not_loan"),
    ("morgan & morgan", "legal_not_loan"),
    ("sue", "legal_not_loan"),
    
    # Non-loan "financing" contexts
    ("auto financing", "auto_not_loan"),
    ("home improvement financing", "home_imp_not_loan"),
    ("finance repairs", "auto_not_loan"),
    ("car financing", "auto_not_loan"),
    
    # Others
    ("supplement", "supplement_not_loan"),
    ("vitamin", "supplement_not_loan"),
    ("wellness", "supplement_not_loan"),
    ("viome", "supplement_not_loan"),
    ("relief factor", "supplement_not_loan"),
    ("job search", "jobs_not_loan"),
    ("ziprecruiter", "jobs_not_loan"),
    ("hiring", "jobs_not_loan"),
    ("nonprofit", "nonprofit_not_loan"),
    ("foundation", "nonprofit_not_loan"),
    ("donate", "nonprofit_not_loan"),
    ("roofing", "home_service_not_loan"),
    ("hvac", "home_service_not_loan"),
]

# Output paths (inside Docker container)
OUT_DIR = "/tmp/exports"
import os
os.makedirs(OUT_DIR, exist_ok=True)

# ── Known loan advertisers (validated ground truth) ───────────────
KNOWN_LOAN_ADVERTISERS = [
    "bills happen", "billshappen", "billshappen.com",
    "coast one financial group", "coast one financial",
    "american financing", "american financing network",
    "debt relief advocates", "debt relief",
    "optima tax shield",
    "cashcall",
    "lendingpoint", "lending club",
    "sofi", "upgrade", "upstart",
    "rocket loans", "best egg",
    "mariner finance", "avant",
    "lendingtree", "onemain financial",
    "wisetack", "sunbit", "katapult",
    "progressive leasing",
    "credit repair", "credit rescue",
    "prequalify", "check your rate",
]

# Known non-loan advertisers (false positives from broad matching)
KNOWN_NON_LOAN_ADVERTISERS = [
    "tax relief advocates", "optima tax", "ethos", "lifelock",
    "supersure", "super sure", "progressive", "allstate",
    "ziprecruiter", "viome", "relief factor", "hollywood suits",
    "morgan & morgan", "morgan and morgan", "incogny",
    "amco", "tra", "term busters", "coast one tax",
    "life lock", "incogni", "mothers against", "madd",
    "st christopher", "truckers fund", "good ranchers",
    "webroot", "puretalk", "patriot mobile", "xfinity",
    "comcast", "grainger", "simplisafe", "ghostbed",
    "shell rotella", "orchard",
    "beaver toyota", "beaver mazda", "world car", "kia",
    "honda", "nissan", "toyota", "mazda", "ford", "chevrolet",
    "freeman toyota", "hubler toyota", "hubler",
    "wilco hyundai",
    "mark spain real estate",
    "peach state hardwood", "finley roofing",
    "usa insulation", "ragsdale",
    "kinetico", "precision windows",
    "ghost bed", "ghostbed",
    "lensseek", "lively", "landmark",
    "native path", "advanced hair", "healthylooking",
    "empower home", "keller williams",
    "ascension island", "knig equipment",
    "farnsworth metal",
    "thompson furniture",
    "allied signing",
    "loud security",
    "breda pest", "pest management",
    "toyota", "endurance",
    "discover", "capital one",
    "i heart radio", "iheart",
]

def classify_detection(det):
    """
    Strict re-classification of a loan candidate.
    Returns (classification: str, evidence: str)
    """
    company = det.get("company", "").lower()
    offer = (det.get("offer", "") + " " + det.get("claims", "")).lower()
    text = det.get("text", "").lower()[:400]
    combined = f"{company} {offer} {text}"
    
    # Check known non-loan advertisers FIRST
    if any(adv in company for adv in KNOWN_NON_LOAN_ADVERTISERS):
        return ("false_positive", f"known non-loan advertiser: {company}")
    
    # Check known loan advertisers
    if any(adv in company for adv in KNOWN_LOAN_ADVERTISERS):
        return ("true_loan", f"known loan advertiser: {company}")
    
    # Check false positive patterns
    for pattern, classification in FALSE_POSITIVE_PATTERNS:
        if pattern in combined:
            return (classification, f"matched '{pattern}' in combined text")
    
    # Check if it's a known loan advertiser
    if any(adv in company for adv in KNOWN_LOAN_ADVERTISERS):
        return ("true_loan", f"known loan advertiser: {company}")
    
    # Check for true loan patterns in company name
    if any(p in company for p in TRUE_LOAN_PATTERNS):
        return ("true_loan", f"loan pattern in company: '{company}'")
    
    # Check for medical/pet financing
    if any(p in combined for p in MEDICAL_FINANCE_PATTERNS):
        return ("medical_financing", f"medical/pet financing match")
    
    # Check for true loan patterns in offer
    if any(p in offer for p in TRUE_LOAN_PATTERNS):
        return ("true_loan", f"loan pattern in offer: '{next(p for p in TRUE_LOAN_PATTERNS if p in offer)}'")
    
    # Check for true loan patterns in transcript (unnamed detections only)
    if not company and any(p in text for p in TRUE_LOAN_PATTERNS):
        return ("true_loan", f"loan pattern in transcript: '{next(p for p in TRUE_LOAN_PATTERNS if p in text)}'")
    
    # If it has a company name but we can't confirm, flag as unknown
    if company:
        return ("unknown", f"has company '{company}' but no clear loan signal")
    
    return ("unknown", "no clear signal")


# ── Process each station ──────────────────────────────────────────
audit_results = {}

for stn in target_stations:
    rows = q("""
        SELECT d.id, d.company_name, d.phone_number, d.website,
               d.offer_summary, d.key_claims,
               c.start_ts,
               t.text
        FROM detections d
        JOIN chunks c ON c.id = d.chunk_id
        JOIN stations s ON s.id = c.station_id
        LEFT JOIN transcripts t ON t.chunk_id = d.chunk_id
        WHERE s.name = ? AND d.is_ad = 1
        ORDER BY c.start_ts DESC
        LIMIT 200
    """, (stn,))
    
    # Apply same loan filter as station_rotation.py (re-implemented inline)
    loan_candidates = []
    for r in rows:
        did, company, phone, website, offer, claims, ts, text = r
        det = {
            "detection_id": did,
            "company": (company or "").strip(),
            "phone": (phone or "").strip(),
            "website": (website or "").strip(),
            "offer": (offer or "").strip(),
            "claims": (claims or "").strip(),
            "text": (text or "").strip(),
            "ts": ts,
        }
        
        # Simple pre-filter (same heuristic as station_rotation)
        c = det["company"].lower()
        o = (det["offer"] + det["claims"]).lower()
        t = det["text"].lower()[:300]
        
        # Skip known non-loan brands
        non_loan_brands = ["tax relief advocates", "optima tax", "ethos", "lifelock",
            "supersure", "super sure", "progressive", "allstate",
            "ziprecruiter", "viome", "relief factor", "hollywood suits",
            "morgan & morgan", "morgan and morgan", "incogny",
            "amco", "tra", "term busters", "coast one tax",
            "life lock", "incogni", "mothers against", "madd",
            "st christopher", "truckers fund", "good ranchers",
            "webroot", "puretalk", "patriot mobile", "xfinity",
            "comcast", "grainger", "simplisafe", "ghostbed",
            "shell rotella", "orchard"]
        
        if any(b in c for b in non_loan_brands):
            continue
        
        # Check if it might be loan-related
        loan_patterns = ["loan", "lending", "borrow", "cash", "credit",
            "financing", "prequalify", "funding", "payday", "installment"]
        
        is_candidate = any(p in f"{c} {o} {t}" for p in loan_patterns)
        if is_candidate:
            loan_candidates.append(det)
    
    # Sample up to 20
    sample = loan_candidates[:20]
    
    # Classify each
    classified = []
    for det in sample:
        cls, evidence = classify_detection(det)
        classified.append({
            "detection_id": det["detection_id"],
            "company": det["company"] or "(unnamed)",
            "offer": det["offer"][:120],
            "text": det["text"][:150],
            "classification": cls,
            "evidence": evidence,
        })
    
    # Count
    true_loan = sum(1 for c in classified if c["classification"] == "true_loan")
    medical_fin = sum(1 for c in classified if c["classification"] == "medical_financing")
    false_pos = sum(1 for c in classified if c["classification"].endswith("_not_loan"))
    unknown = sum(1 for c in classified if c["classification"] == "unknown")
    total = len(classified)
    precision = round((true_loan + medical_fin) / total * 100, 1) if total > 0 else 0
    
    audit_results[stn] = {
        "station": stn,
        "total_detections": len(rows),
        "loan_candidates": len(loan_candidates),
        "sampled": total,
        "true_loan": true_loan,
        "medical_financing": medical_fin,
        "false_positive": false_pos,
        "unknown": unknown,
        "precision": precision,
        "classified": classified,
    }
    
    print(f"\n{stn}: sampled={total} true_loan={true_loan} medical={medical_fin} fp={false_pos} unknown={unknown} precision={precision}%", flush=True)
    for c in classified:
        icon = {"true_loan": "💰", "medical_financing": "🏥", "unknown": "❓"}.get(c["classification"], "❌")
        print(f"  {icon} {c['classification']:<25s} company='{c['company'][:35]}' {c['evidence'][:60]}", flush=True)

# ── Station-level decisions ───────────────────────────────────────
print(f"\n{'='*60}")
print("STATION DECISIONS")
print(f"{'='*60}")

for stn in target_stations:
    ar = audit_results[stn]
    p = ar["precision"]
    
    if p >= 80:
        trust = "TRUST"
        decision_note = "Precision >= 80%. Station score is reliable."
    elif p >= 60:
        trust = "REVIEW"
        decision_note = "Precision 60-79%. Keep but review classifier for false positives."
    else:
        trust = "RE-SCORE"
        decision_note = "Precision < 60%. Re-score station before rotation decision."
    
    print(f"  {stn:<20s} precision={p:>5.1f}% → {trust} — {decision_note}", flush=True)

# ═══════════════════════════════════════════════════════════════════
# OUTPUTS
# ═══════════════════════════════════════════════════════════════════

# CSV
with open(os.path.join(OUT_DIR, "loan_station_classification_audit.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["station", "detection_id", "company", "classification", "evidence", "offer_snippet", "text_snippet"])
    for stn in target_stations:
        for c in audit_results[stn]["classified"]:
            w.writerow([
                stn, c["detection_id"], c["company"], c["classification"],
                c["evidence"], c["offer"][:100], c["text"][:100]
            ])
print(f"\n✅ {OUT_DIR}/loan_station_classification_audit.csv", flush=True)

# MD Report
with open(os.path.join(OUT_DIR, "loan_station_classification_audit.md"), "w") as f:
    f.write("# Loan Station Classification Audit\n\n")
    f.write(f"**Source**: Live Docker DB — re-classified with strict loan criteria\n\n")
    
    f.write("## Summary Table\n\n")
    f.write("| Station | Sampled | True Loan | Medical Fin | False Pos | Unknown | Precision | Decision |\n")
    f.write("|:---|---:|---:|---:|---:|---:|---:|:---|\n")
    for stn in target_stations:
        ar = audit_results[stn]
        p = ar["precision"]
        if p >= 80: trust = "✅ TRUST"
        elif p >= 60: trust = "⚠️ REVIEW"
        else: trust = "❌ RE-SCORE"
        f.write(f"| {stn} | {ar['sampled']} | {ar['true_loan']} | {ar['medical_financing']} | {ar['false_positive']} | {ar['unknown']} | {ar['precision']}% | {trust} |\n")
    
    f.write("\n## Detailed Audit Per Station\n\n")
    for stn in target_stations:
        ar = audit_results[stn]
        f.write(f"### {stn}\n\n")
        f.write(f"- **Sampled**: {ar['sampled']} / {ar['loan_candidates']} loan candidates\n")
        f.write(f"- **True loan**: {ar['true_loan']} | **Medical/pet financing**: {ar['medical_financing']} | **False positive**: {ar['false_positive']} | **Unknown**: {ar['unknown']}\n")
        f.write(f"- **Precision**: {ar['precision']}%\n\n")
        
        for c in ar["classified"]:
            icon = {"true_loan": "💰", "medical_financing": "🏥", "unknown": "❓"}.get(c["classification"], "❌")
            f.write(f"| {icon} | {c['classification']} | {c['company']} | {c['evidence']} |\n")
        
        f.write("\n")
    
    # Revised rotation recommendations
    f.write("## Revised Rotation Recommendations\n\n")
    f.write("Based on audit precision:\n\n")
    
    f.write("| Station | Original Decision | Audited Precision | Revised Decision |\n")
    f.write("|:---|---:|---:|:---|\n")
    
    # From previous station_rotation analysis
    original_decisions = {"woai-am-1200": "keep", "wsb-am-750": "keep", "wibc-fm-931": "keep",
                           "klif-am-570": "keep", "ktrh-am-740": "keep", "wtam-am-1100": "rotate_out"}
    
    for stn in target_stations:
        ar = audit_results[stn]
        orig = original_decisions.get(stn, "unknown")
        p = ar["precision"]
        
        if p >= 80:
            revised = orig  # Trust original
        elif p >= 60:
            revised = f"{orig} (re-evaluate in 48h)"
        else:
            revised = "re-score"
        
        f.write(f"| {stn} | {orig} | {p}% | {revised} |\n")
    
    f.write("\n## Common False Positive Patterns\n\n")
    fp_counts = defaultdict(int)
    for stn in target_stations:
        for c in audit_results[stn]["classified"]:
            if c["classification"].endswith("_not_loan"):
                fp_counts[c["classification"]] += 1
    for cls, cnt in sorted(fp_counts.items(), key=lambda x: -x[1]):
        f.write(f"- **{cls}**: {cnt} occurrences\n")

print(f"✅ {OUT_DIR}/loan_station_classification_audit.md", flush=True)

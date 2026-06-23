"""
Query live Docker DB for loan-classified detections on audit stations.
Gets full context (company, offer, transcript) for manual re-classification.
"""
import sqlite3
import json

DB = "/app/data/pipeline.db"

def q(sql, params=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    if params:
        c.execute(sql, params)
    else:
        c.execute(sql)
    rows = c.fetchall()
    conn.close()
    return rows

# Stations to audit
target_stations = ["woai-am-1200", "wsb-am-750", "wibc-fm-931", "klif-am-570", "ktrh-am-740", "wtam-am-1100"]

# ── Loan detection keyword patterns (same as station_rotation.py) ──
LOAN_PATTERNS_OFFER = [
    "personal loan", "installment loan", "payday loan", "cash advance",
    "bad credit", "emergency cash", "same day funding", "borrow money",
    "get cash", "quick funding", "loan", "borrow", "financing",
    "credit check", "prequalify", "check your rate",
]

LOAN_PATTERNS_TEXT = [
    "personal loan", "installment loan", "payday loan", "cash advance",
    "bad credit", "emergency cash", "same-day funding",
    "borrow", "get cash today", "loan", "credit check",
    "prequalify", "check your rate", "soft credit check",
    "bills happen", "apply now",
]

NOT_LOAN_BRANDS = ["tax relief advocates", "optima tax", "ethos", "lifelock",
    "supersure", "progressive", "allstate", "ziprecruiter", "viome",
    "relief factor", "hollywood suits", "morgan", "incogny",
    "amco", "tra", "term busters", "coast one tax",
    "life lock", "incogni", "mothers against", "madd",
    "st christopher", "truckers fund"]

print("=== LOAN-CLASSIFIED DETECTIONS PER STATION ===", flush=True)

for stn in target_stations:
    # Query all detections on this station with is_ad=1
    rows = q("""
        SELECT d.id, d.company_name, d.phone_number, d.website,
               d.offer_summary, d.key_claims,
               c.start_ts,
               t.text
        FROM detections d
        JOIN chunks c ON c.id = d.chunk_id
        JOIN stations s ON s.id = c.station_id
        LEFT JOIN transcripts t ON t.chunk_id = d.chunk_id
        WHERE s.name = ?
          AND d.is_ad = 1
        ORDER BY c.start_ts DESC
        LIMIT 200
    """, (stn,))
    
    # Apply same loan classification as in station_rotation.py
    loan_dets = []
    for r in rows:
        did, company, phone, website, offer, claims, ts, text = r
        company = (company or "").strip().lower()
        offer_str = ((offer or "") + " " + (claims or "")).strip().lower()
        text_str = (text or "").strip().lower()[:300]
        
        # Skip known non-loan brands
        if any(b in company for b in NOT_LOAN_BRANDS):
            continue
        
        is_loan = False
        reason = ""
        
        if any(p in offer_str for p in LOAN_PATTERNS_OFFER):
            is_loan = True
            reason = "offer_match"
        elif any(p in company for p in ["personal loan", "installment loan", "payday loan",
                  "cash advance", "bad credit loan", "emergency loan", "same day funding",
                  "same day loan", "cash loan", "quick cash", "borrow money", "loan network",
                  "bills happen", "billshappen", "debt relief", "debt settlement",
                  "credit repair", "credit rescue"]):
            is_loan = True
            reason = "company_match"
        elif not company and any(p in text_str for p in LOAN_PATTERNS_TEXT):
            is_loan = True
            reason = "text_match"
        
        if is_loan:
            loan_dets.append({
                "detection_id": did,
                "company": company or "(unnamed)",
                "phone": phone or "",
                "website": website or "",
                "offer": offer or "",
                "claims": claims or "",
                "text": text or "",
                "ts": ts,
                "reason": reason
            })
    
    print(f"\n{stn}: {len(rows)} total detections, {len(loan_dets)} loan-classified")
    
    # Sample up to 20
    sample = loan_dets[:20]
    for det in sample:
        print(f"  [{det['reason']}] id={det['detection_id']} company='{det['company'][:40]}' offer='{det['offer'][:80]}' text='{det['text'][:100]}'")

print("\n=== DONE ===", flush=True)

"""
Strict loan-only classifier for station rotation.
Phrase-level matching only. No single-word matching.
Returns structured result with confidence level and matched patterns.
"""
import re

# ═══════════════════════════════════════════════════════════════════
# STRICT LOAN PATTERNS — phrase-level only
# ═══════════════════════════════════════════════════════════════════
LOAN_PATTERNS = [
    # Personal / installment / payday
    "personal loan",
    "personal loans",
    "installment loan",
    "installment loans",
    "payday loan",
    "payday loans",
    "cash advance",
    "cash advances",
    "short term loan",
    "short term loans",
    "short-term loan",
    "short-term loans",
    "online loan",
    "online loans",
    
    # Bad credit / emergency
    "bad credit loan",
    "bad credit loans",
    "emergency loan",
    "emergency loans",
    "emergency cash",
    "same day loan",
    "same day loans",
    "same day funding",
    "same-day funding",
    "same day cash",
    
    # Borrowing
    "borrow money",
    "borrow up to",
    "get cash now",
    "get cash today",
    "cash loan",
    "cash loans",
    "quick cash",
    "fast cash",
    
    # Loan application
    "loan request",
    "request a loan",
    "apply for a loan",
    "apply online for a loan",
    "loan offer",
    "loan offers",
    "loan matching",
    
    # Loan networks / known lenders
    "loan network",
    "loan matching service",
    "bills happen",
    "billshappen",
    "american financing",
    "debt relief advocates",
    "debt relief",
    
    # Soft credit / prequalify (loan context only — exclude from credit card)
    "prequalify",
    "check your rate",
    "soft credit check",
    "no credit check loan",
    "no credit check loans",
]

# ═══════════════════════════════════════════════════════════════════
# NEGATIVE EXCLUSIONS — if any match, NOT a loan
# ═══════════════════════════════════════════════════════════════════
EXCLUSION_PATTERNS = [
    # Auto / dealer
    "car",
    "auto",
    "vehicle",
    "toyota",
    "kia",
    "hyundai",
    "honda",
    "nissan",
    "mazda",
    "ford",
    "chevrolet",
    "dealer",
    "dealership",
    "lease",
    "truck",
    
    # Home services
    "roofing",
    "windows",
    "hvac",
    "plumbing",
    "bath",
    "remodel",
    "solar",
    "mattress",
    "furniture",
    "garage door",
    "insulation",
    "flooring",
    "pest control",
    "pest management",
    
    # Supplements / health
    "supplement",
    "vitamin",
    "viome",
    "wellness",
    "green tea",
    "curcumin",
    "resveratrol",
    "relief factor",
    "probiotic",
    "ghostbed",
    "healthylooking",
    
    # Tax / IRS
    "tax",
    "irs",
    "tax relief",
    "tax debt",
    "tax resolution",
    "tax attorney",
    "optima tax",
    "tax relief advocates",
    
    # Insurance
    "insurance",
    "life insurance",
    "term life",
    "ethos",
    "medicare",
    "progressive",
    "allstate",
    "supersure",
    
    # Legal
    "attorney",
    "lawyer",
    "law firm",
    "lawsuit",
    "class action",
    "injury",
    "sue",
    "legal",
    
    # Identity / credit monitoring
    "lifelock",
    "identity theft",
    "identity protection",
    "credit card",
    "discover",
    "capital one",
    
    # Nonprofit
    "foundation",
    "nonprofit",
    "non profit",
    "charity",
    "donate",
    "donation",
    
    # Jobs / recruiting
    "ziprecruiter",
    "hiring",
    "job search",
    "career",
    
    # Media / internal
    "iheart",
    "hannity",
    "bongino",
    "talk radio",
    "podcast",
]

# ═══════════════════════════════════════════════════════════════════
# KNOWN LOAN BRANDS (validated, skip exclusion check)
# ═══════════════════════════════════════════════════════════════════
KNOWN_LOAN_BRANDS = [
    "american financing",
    "debt relief advocates",
    "bills happen",
    "billshappen",
    "billshappen.com",
]

# ═══════════════════════════════════════════════════════════════════
# CLASSIFIER
# ═══════════════════════════════════════════════════════════════════

def classify_loan(company="", offer="", text=""):
    """
    Strict loan classifier.
    
    Args:
        company: Company name (lowercased)
        offer: Offer/claims text (lowercased)
        text: Transcript text (lowercased)
    
    Returns:
        dict with:
            - classification: str (true_loan, loan_possible, not_loan, excluded_noise)
            - is_loan: bool
            - matched_positive: list[str] or None
            - matched_negative: list[str] or None
            - reason: str
    """
    company = (company or "").lower().strip()
    offer = (offer or "").lower().strip()
    text = (text or "").lower().strip()
    combined = f"{company} {offer} {text}"
    
    # ── Step 1: Check known loan brands (bypass exclusions) ──
    for brand in KNOWN_LOAN_BRANDS:
        if brand in company or brand in combined:
            return {
                "classification": "true_loan",
                "is_loan": True,
                "matched_positive": [brand],
                "matched_negative": None,
                "reason": f"Known loan brand: '{brand}'"
            }
    
    # ── Step 2: Collect all matched loan patterns ──
    matched_positive = []
    for pattern in LOAN_PATTERNS:
        if pattern in combined:
            matched_positive.append(pattern)
    
    # ── Step 3: Collect all matched exclusion patterns ──
    matched_negative = []
    for pattern in EXCLUSION_PATTERNS:
        if pattern in combined:
            matched_negative.append(pattern)
    
    # ── Step 4: No loan patterns → not a loan ──
    if not matched_positive:
        return {
            "classification": "not_loan",
            "is_loan": False,
            "matched_positive": None,
            "matched_negative": matched_negative if matched_negative else None,
            "reason": "No loan patterns matched"
        }
    
    # ── Step 5: Exclusion patterns override loan (unless loan pattern is very specific) ──
    if matched_negative:
        # If the positive match is very specific (2+ words), still flag as possible
        strongest = max(matched_positive, key=len)
        if len(strongest.split()) >= 2:
            return {
                "classification": "loan_possible",
                "is_loan": True,
                "matched_positive": matched_positive,
                "matched_negative": matched_negative,
                "reason": f"Loan '{strongest}' but exclusion '{matched_negative[0]}' present"
            }
        
        return {
            "classification": "excluded_noise",
            "is_loan": False,
            "matched_positive": matched_positive,
            "matched_negative": matched_negative,
            "reason": f"Excluded by '{matched_negative[0]}' despite '{matched_positive[0]}'"
        }
    
    # ── Step 6: Clean match ──
    strongest = max(matched_positive, key=len)
    return {
        "classification": "true_loan",
        "is_loan": True,
        "matched_positive": matched_positive,
        "matched_negative": None,
        "reason": f"Matched '{strongest}'"
    }


# ═══════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════

def run_tests():
    """Run built-in test cases."""
    test_cases = [
        # (company, offer, text, expected_is_loan, expected_classification)
        
        # === Should classify as TRUE LOAN ===
        ("", "Apply for a personal loan today", "", True, "true_loan"),
        ("", "Bad credit loan options are available", "", True, "true_loan"),
        ("", "Get emergency cash with an installment loan", "", True, "true_loan"),
        ("BillsHappen.com", "personal loans available", "", True, "true_loan"),
        ("", "Request a loan online today", "", True, "true_loan"),
        ("American Financing", "", "", True, "true_loan"),
        ("", "get cash now with same day funding", "", True, "true_loan"),
        ("", "short term loan bad credit OK", "", True, "true_loan"),
        ("", "online loans apply now", "", True, "true_loan"),
        ("", "borrow up to $5000 today", "", True, "true_loan"),
        ("Debt Relief Advocates", "", "", True, "true_loan"),
        
        # === Should NOT classify as loan ===
        ("Toyota", "financing available", "", False, "not_loan"),
        ("", "Get roofing financing", "", False, "not_loan"),
        ("", "Check your credit card offer", "", False, "not_loan"),
        ("", "Tax relief for IRS debt", "", False, "not_loan"),
        ("Ethos", "life insurance quote", "", False, "not_loan"),
        ("", "Call an attorney today", "", False, "not_loan"),
        ("Viome", "health supplement", "", False, "not_loan"),
        ("", "Capital One credit card", "", False, "not_loan"),
        ("", "Auto loan dealership special", "", False, "not_loan"),
        ("", "donate to our foundation", "", False, "not_loan"),
        ("", "hiring now apply today", "", False, "not_loan"),
        ("", "wellness and vitamins", "", False, "not_loan"),
        ("", "irs tax debt help", "", False, "not_loan"),
        ("Progressive", "auto insurance", "", False, "not_loan"),
        
        # === Edge cases ===
        # Loan phrase + exclusion → not_loan (single words aren't in LOAN_PATTERNS)
        ("", "get a loan for car repairs", "", False, "not_loan"),
        # Very specific loan phrase → possible even with exclusion
        ("", "apply for a personal loan for car repairs", "", True, "loan_possible"),
        # Known brand bypasses exclusion
        ("American Financing", "car financing", "", True, "true_loan"),
        # Empty → not loan
        ("", "", "", False, "not_loan"),
    ]
    
    passed = 0
    failed = 0
    
    for i, (company, offer, text, expected_loan, expected_class) in enumerate(test_cases, 1):
        result = classify_loan(company=company, offer=offer, text=text)
        loan_ok = result["is_loan"] == expected_loan
        class_ok = result["classification"] == expected_class
        
        if loan_ok and class_ok:
            passed += 1
        else:
            failed += 1
            detail = f"is_loan={result['is_loan']}(expected {expected_loan}) class={result['classification']}(expected {expected_class})"
            print(f"  ❌ Test {i}: '{company}' / '{offer}' / '{text}' → {detail}", flush=True)
    
    print(f"\n  Tests: {passed} passed, {failed} failed", flush=True)
    return failed == 0


if __name__ == "__main__":
    print("Running loan classifier tests...", flush=True)
    success = run_tests()
    print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed'}", flush=True)

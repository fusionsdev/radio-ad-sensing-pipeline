"""Verify key classifications are correct."""
import json

candidates = [json.loads(l) for l in open("data/radio_keyword_entity_master.jsonl")]

# Check specific companies
checks = [
    "LifeLock", "Tax Relief Advocates", "Wesley Financial Group", "Hoffman Financial",
    "AutoZone", "Plexiderm", "Spartan Construction", "Trajan Wealth",
    "Good Ranchers", "Better Addiction Care", "Ethos", "Incogny",
    "Morgan & Morgan", "Debt Relief Advocates", "American Financing",
    "Vincent Financial Group", "DFW Retirement Planners", "Nicholas Wealth",
    "Lockwood Capital"
]

results = {}
for e in candidates:
    cn = e["company_name"].lower()
    for check in checks:
        if check.lower() in cn:
            results[check] = e

print(f"{'Check':<35} {'Vertical':<30} {'Status'}")
print("-" * 80)
for check in checks:
    if check in results:
        e = results[check]
        target = e["vertical"]
        report = e["reporting_status"]
        
        # Determine if classification is correct
        ok = True
        if check == "LifeLock" and target != "identity_protection": ok = False
        if check == "Tax Relief Advocates" and target != "tax_relief": ok = False
        if check in ["Wesley Financial Group", "Hoffman Financial"] and target != "unknown_financial_review": ok = False
        if check in ["Vincent Financial Group", "DFW Retirement Planners", "Nicholas Wealth", "Lockwood Capital"] and target != "unknown_financial_review": ok = False
        if check == "Trajan Wealth" and target != "unknown_financial_review": ok = False
        if check == "AutoZone" and target != "automotive_non_financing": ok = False
        if check == "Plexiderm" and target != "health_supplement": ok = False
        if check == "Spartan Construction" and target != "home_service": ok = False
        if check == "Good Ranchers" and target != "retail": ok = False
        if check == "Better Addiction Care" and target != "medical_non_financing": ok = False
        if check == "Ethos" and target != "insurance": ok = False
        if check == "Incogny" and target != "identity_protection": ok = False
        if check == "Morgan & Morgan" and target != "legal_financial": ok = False
        
        marker = "✅" if ok else "❌"
        print(f"{marker} {check:<33} {target:<30} {report}")

# Also check financial report top entries
print(f"\n=== Top 20 Financial (report_now) ===")
fin = [e for e in candidates if e["reporting_status"] == "report_now"]
fin.sort(key=lambda x: -x["detections"])
print(f"{'Count':>5} {'Company':<35} {'Vertical':<25}")
print("-" * 70)
for e in fin[:20]:
    print(f"{e['detections']:>5} {e['company_name']:<35} {e['vertical']:<25}")

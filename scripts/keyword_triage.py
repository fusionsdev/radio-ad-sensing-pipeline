"""One-off keyword triage for exports/keyword_candidates_current.csv"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

PERSONAL_LOAN_LENDERS = {
    "onemain finance corporation",
    "sofi technologies, inc.",
    "billshappen.com",
    "fc holdco llc",
    "clgf holdco 1, llc",
    "ld holdings group, llc",
    "cl holdings llc",
    "w&a intermediate co., llc",
    "bread financial holdings, inc.",
}
AUTO_FINANCE = {
    "credit acceptance corporation",
    "bridgecrest acceptance corporation",
    "exeter finance, llc.",
    "westlake services, llc",
    "american credit acceptance, llc",
    "byrider franchising, llc",
    "hyundai capital america",
    "toyota motor credit corporation",
    "nissan motor acceptance company llc",
    "american honda finance corp",
    "general motors financial company, inc.",
    "ally financial inc.",
    "santander holdings usa, inc.",
}
MORTGAGE = {
    "rocket mortgage, llc",
    "freedom mortgage company",
    "mr. cooper group inc.",
    "shellpoint partners, llc",
    "select portfolio servicing, inc.",
    "roundpoint mortgage servicing llc",
    "loancare, llc",
    "ocwen financial corporation",
    "pennymac loan services, llc.",
    "carrington mortgage services, llc",
    "bsi financial holdings, inc.",
    "selene holdings llc",
}
DEBT_COLLECTORS = {
    "encore capital group inc.",
    "portfolio recovery associates, llc",
    "resurgent capital services l.p.",
    "transworld systems inc",
    "national credit systems,inc.",
    "i.c. system, inc.",
}
CREDIT_BUREAUS = {
    "equifax, inc.",
    "experian information solutions inc.",
    "transunion intermediate holdings, inc.",
}
CRYPTO_FINTECH = {
    "coinbase, inc.",
    "block, inc.",
    "robinhood markets inc.",
    "paypal holdings, inc",
    "chime financial inc",
    "transferwise ltd",
    "early warning services, llc",
    "foris dax, inc.",
}
BIG_BANKS = {
    "jpmorgan chase & co.",
    "wells fargo & company",
    "bank of america, national association",
    "citibank, n.a.",
    "capital one financial corporation",
    "discover bank",
    "u.s. bancorp",
    "fifth third financial corporation",
    "truist financial corporation",
    "td bank us holding company",
    "pnc bank n.a.",
    "bmo bank national association",
    "new york community bancorp inc",
    "navy federal credit union",
    "united services automobile association",
    "goldman sachs bank usa",
    "citizens financial group, inc.",
    "huntington national bank, the",
    "american express company",
    "synchrony financial",
    "barclays bank delaware",
}
AUTO_DEALERS = {"carmax, inc.", "carvana group, llc"}


def classify_entity(entity: str) -> str:
    e = entity.strip().lower()
    if e in PERSONAL_LOAN_LENDERS:
        return "personal_loan"
    if e in AUTO_FINANCE:
        return "auto_finance"
    if e in MORTGAGE:
        return "mortgage"
    if e in DEBT_COLLECTORS:
        return "debt_collector"
    if e in CREDIT_BUREAUS:
        return "credit_bureau"
    if e in CRYPTO_FINTECH:
        return "crypto_fintech"
    if e in BIG_BANKS:
        return "big_bank"
    if e in AUTO_DEALERS:
        return "auto_dealer"
    return "other"


def triage(row: dict) -> dict:
    variant = row["variant_type"]
    source = row["source_type"]
    entity = row["entity_name"]
    eclass = classify_entity(entity)
    is_radio = source == "radio_transcript"

    if variant in ("complaints", "reviews", "bbb", "phone_number", "contact"):
        return {
            "intent": "low intent / informational",
            "value": 1,
            "risk": "low-quality traffic",
            "action": "reject",
            "match": "—",
            "ad_group": "—",
            "reason": f"Support/navigational variant ({variant}); zero loan acquisition intent",
        }

    if is_radio:
        if variant == "brand":
            return {
                "intent": "brand/trademark intent",
                "value": 5,
                "risk": "trademark; misleading if impersonating",
                "action": "hold_for_manual_review",
                "match": "exact",
                "ad_group": "Brand Intent — Billshappen",
                "reason": "Verified radio personal-loan advertiser; high brand search volume; trademark review before ad copy",
            }
        if variant == "product":
            return {
                "intent": "direct loan intent",
                "value": 5,
                "risk": "trademark; policy",
                "action": "approve_for_ads",
                "match": "phrase",
                "ad_group": "Brand Intent — Billshappen",
                "reason": "Product + brand from live radio ad; direct personal-loan intent; launch with comparison LP + trademark-safe copy",
            }
        if variant == "alternative":
            return {
                "intent": "problem-aware intent",
                "value": 4,
                "risk": "trademark; misleading-risk",
                "action": "approve_for_research",
                "match": "phrase",
                "ad_group": "Brand Intent — Billshappen",
                "reason": "Comparison intent against known radio advertiser; test competitor/alternative LP",
            }
        if variant == "intent":
            return {
                "intent": "problem-aware intent",
                "value": 4,
                "risk": "misleading-risk",
                "action": "approve_for_research",
                "match": "phrase",
                "ad_group": "Brand Intent — Billshappen",
                "reason": "Legitimacy research intent; funnel to comparison/review LP not impersonation",
            }

    if variant == "alternative":
        short = entity.split(",")[0][:24]
        if eclass in ("personal_loan", "debt_collector"):
            return {
                "intent": "problem-aware intent",
                "value": 3,
                "risk": "trademark; misleading-risk",
                "action": "approve_for_research",
                "match": "phrase",
                "ad_group": f"Alternatives — {short}",
                "reason": "Alternative/comparison SERP; affiliate-friendly if LP is honest comparison",
            }
        if eclass == "big_bank":
            return {
                "intent": "brand/trademark intent",
                "value": 3,
                "risk": "trademark; policy",
                "action": "hold_for_manual_review",
                "match": "phrase",
                "ad_group": "Brand Intent — Major Lenders",
                "reason": "Bank alternative queries have volume but trademark + financial services policy risk",
            }
        return {
            "intent": "brand/trademark intent",
            "value": 2,
            "risk": "trademark",
            "action": "reject",
            "match": "—",
            "ad_group": "—",
            "reason": "Alternative query outside core loan vertical or low affiliate monetization",
        }

    if variant == "brand":
        if eclass == "personal_loan":
            return {
                "intent": "brand/trademark intent",
                "value": 4,
                "risk": "trademark",
                "action": "hold_for_manual_review",
                "match": "exact",
                "ad_group": "Brand Intent — Installment Loan",
                "reason": "Known installment/personal lender; brand traffic monetizable via comparison LP",
            }
        if eclass == "debt_collector":
            return {
                "intent": "problem-aware intent",
                "value": 3,
                "risk": "trademark; misleading-risk",
                "action": "approve_for_research",
                "match": "phrase",
                "ad_group": "Debt / Tax Relief",
                "reason": "Debt collector brand searches often precede debt relief/loan consolidation intent",
            }
        if eclass == "big_bank":
            return {
                "intent": "brand/trademark intent",
                "value": 3,
                "risk": "trademark; policy",
                "action": "hold_for_manual_review",
                "match": "exact",
                "ad_group": "Brand Intent — Major Lenders",
                "reason": "High volume brand terms; only viable with non-impersonation comparison funnel",
            }
        if eclass == "mortgage":
            return {
                "intent": "brand/trademark intent",
                "value": 2,
                "risk": "trademark; off-vertical",
                "action": "reject",
                "match": "—",
                "ad_group": "—",
                "reason": "Mortgage servicer brand; outside personal/installment loan vertical",
            }
        if eclass in ("auto_finance", "auto_dealer"):
            return {
                "intent": "brand/trademark intent",
                "value": 1,
                "risk": "off-vertical",
                "action": "reject",
                "match": "—",
                "ad_group": "—",
                "reason": "Auto finance/dealer brand; not in target verticals",
            }
        if eclass == "credit_bureau":
            return {
                "intent": "irrelevant",
                "value": 1,
                "risk": "trademark; off-vertical",
                "action": "reject",
                "match": "—",
                "ad_group": "—",
                "reason": "Credit bureau brand; credit monitoring intent not loan acquisition",
            }
        if eclass == "crypto_fintech":
            return {
                "intent": "irrelevant",
                "value": 1,
                "risk": "off-vertical",
                "action": "reject",
                "match": "—",
                "ad_group": "—",
                "reason": "Crypto/payments brand; no loan vertical fit",
            }
        return {
            "intent": "brand/trademark intent",
            "value": 2,
            "risk": "trademark",
            "action": "reject",
            "match": "—",
            "ad_group": "—",
            "reason": "Obscure holdco/legal entity name; low search volume, unclear loan intent",
        }

    return {
        "intent": "irrelevant",
        "value": 1,
        "risk": "unknown",
        "action": "reject",
        "match": "—",
        "ad_group": "—",
        "reason": "Unclassified variant",
    }


def main() -> None:
    csv_path = Path("exports/keyword_candidates_current.csv")
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    results = [{**r, **triage(r)} for r in rows]

    actions = defaultdict(int)
    for r in results:
        actions[r["action"]] += 1

    top = sorted(
        [r for r in results if r["action"] != "reject"],
        key=lambda x: (-x["value"], -float(x["score"])),
    )[:10]

    lines = []
    lines.append("# Keyword Triage Report")
    lines.append("")
    lines.append("**Source:** `exports/keyword_candidates_current.csv` (449 candidates · 11 radio_transcript · 438 cfpb_complaint seed)")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append(f"- **Total keywords:** {len(results)}")
    lines.append(f"- **approve_for_ads:** {actions.get('approve_for_ads', 0)}")
    lines.append(f"- **approve_for_research:** {actions.get('approve_for_research', 0)}")
    lines.append(f"- **hold_for_manual_review:** {actions.get('hold_for_manual_review', 0)}")
    lines.append(f"- **reject:** {actions.get('reject', 0)}")
    lines.append("")
    lines.append("**Top 10 keywords (by commercial value + pipeline score):**")
    lines.append("")
    for i, r in enumerate(top, 1):
        lines.append(f"{i}. `{r['keyword']}` — {r['action']} (value {r['value']}/5)")
    lines.append("")
    lines.append("## 2. Keyword Decision Table")
    lines.append("")
    lines.append("| keyword | intent | value_score | risk_level | recommended_action | match_type | ad_group | reason |")
    lines.append("|---|---:|---:|---|---|---|---|---|")
    for r in results:
        reason = r["reason"].replace("|", "/")
        lines.append(
            f"| {r['keyword']} | {r['intent']} | {r['value']} | {r['risk']} | {r['action']} | {r['match']} | {r['ad_group']} | {reason} |"
        )

    # Ad groups
    ag_map: dict[str, list[str]] = defaultdict(list)
    ag_intent: dict[str, str] = {}
    ag_lp: dict[str, str] = {
        "Brand Intent — Billshappen": "Radio-verified lender comparison; emphasize rates/terms disclosure, not impersonation",
        "Brand Intent — Installment Loan": "Side-by-side installment lender comparison with soft-pull pre-qual CTA",
        "Brand Intent — Major Lenders": "Major bank personal loan comparison; no logo impersonation",
        "Debt / Tax Relief": "Debt consolidation / settlement vs new loan options",
        "Alternatives — OneMain Finance": "OneMain alternative lenders for bad credit installment",
        "Alternatives — SoFi Technologies": "SoFi alternative for personal loan rate shoppers",
        "Alternatives — Encore Capital": "Debt relief options when dealing with collector",
        "Alternatives — Portfolio Recovery": "Debt negotiation vs consolidation loan paths",
        "Alternatives — Resurgent Capital": "Debt relief funnel for collector-related searches",
        "Alternatives — Transworld Systems": "Debt relief / consolidation comparison",
        "Alternatives — I.C. System": "Debt relief educational LP",
        "Alternatives — National Credit Systems": "Debt relief comparison LP",
        "Alternatives — FC HoldCo LLC": "Installment lender alternatives",
        "Alternatives — CLGF Holdco 1": "Subprime installment alternatives",
        "Alternatives — LD Holdings Group": "Installment/payday alternative comparison",
        "Alternatives — CL Holdings LLC": "Installment lender alternatives",
        "Alternatives — W&A Intermediate Co.": "Installment lender alternatives",
        "Alternatives — Bread Financial": "Retail/installment financing alternatives",
    }
    for r in results:
        if r["action"] == "reject" or r["ad_group"] == "—":
            continue
        ag = r["ad_group"]
        ag_map[ag].append(r["keyword"])
        ag_intent[ag] = r["intent"]

    lines.append("")
    lines.append("## 3. Recommended Ad Groups")
    lines.append("")
    lines.append("| ad_group | keywords | intent | suggested_landing_page_angle |")
    lines.append("|---|---|---|---|")
    for ag in sorted(ag_map.keys()):
        kws = ", ".join(f"`{k}`" for k in ag_map[ag])
        lp = ag_lp.get(ag, "Honest lender comparison with disclosure-first copy")
        lines.append(f"| {ag} | {kws} | {ag_intent[ag]} | {lp} |")

    negatives = [
        ("login", "Existing customer account access"),
        ("sign in", "Navigational support traffic"),
        ("customer service", "Support intent not acquisition"),
        ("phone number", "Contact/support navigational"),
        ("complaint", "CFPB/reputation research not loan intent"),
        ("complaints", "Support/reputation traffic"),
        ("reviews", "Research without conversion intent"),
        ("bbb", "Reputation research"),
        ("lawsuit", "Legal research traffic"),
        ("scam", "Fraud research; high bounce"),
        ("fraud", "Fraud research traffic"),
        ("career", "Job seeker traffic"),
        ("jobs", "Recruitment traffic"),
        ("hiring", "Recruitment traffic"),
        ("app download", "Mobile app install intent"),
        ("stock", "Investor traffic (fintech brands)"),
        ("investor", "IR traffic"),
        ("mortgage", "Off-vertical unless running mortgage campaigns"),
        ("refinance mortgage", "Mortgage not personal loan vertical"),
        ("auto loan", "Auto finance off-vertical"),
        ("car loan", "Auto finance off-vertical"),
        ("crypto", "Crypto off-vertical"),
        ("bitcoin", "Crypto off-vertical"),
    ]
    lines.append("")
    lines.append("## 4. Negative Keywords")
    lines.append("")
    lines.append("| negative_keyword | reason |")
    lines.append("|---|---|")
    for neg, reason in negatives:
        lines.append(f"| {neg} | {reason} |")

    out = Path("exports/keyword_triage_report.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out} ({len(lines)} lines)")
    print("actions", dict(actions))


if __name__ == "__main__":
    main()
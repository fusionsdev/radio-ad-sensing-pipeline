#!/usr/bin/env python3
"""
Test compliance scorer
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.scoring.compliance_score import ComplianceScorer

def test_compliance_scorer():
    scorer = ComplianceScorer()
    
    # Test completeness score
    finding = {
        "apr_found": True,
        "not_lender_found": True,
        "no_guarantee_found": True,
        "credit_check_found": True,
        "state_restriction_found": True,
        "advertiser_disclosure_found": True,
        "page_type": "terms"
    }
    score = scorer.calculate_completeness_score(finding)
    # Should be 20+15+15+10+10+10+10 = 90
    assert score == 90
    
    # Test policy risk score
    finding = {
        "apr_max": 40,  # Over 36
        "risky_claims": "guaranteed approval, no credit check",
        "category": "lead_generator",
        "not_lender_found": False,  # Missing for leadgen
        "apr_found": False,  # Missing APR
        "state_restriction_found": False,  # Missing state restriction
        "credit_check_found": False  # Missing credit check disclosure
    }
    score = scorer.calculate_policy_risk_score(finding)
    # APR max > 36: 20
    # Guaranteed approval: 30
    # No credit check: 25
    # Missing APR disclosure: 15
    # Missing not-lender for leadgen: 15
    # Missing state restriction: 10
    # Missing credit check disclosure: 10
    # Total: 125, capped at 100
    assert score == 100
    
    # Test recommended action
    assert scorer.get_recommended_action(10) == "LOW_RISK"
    assert scorer.get_recommended_action(30) == "REVIEW"
    assert scorer.get_recommended_action(60) == "HIGH_RISK"
    assert scorer.get_recommended_action(80) == "DO_NOT_MODEL"
    
    print("All compliance scorer tests passed!")

if __name__ == "__main__":
    test_compliance_scorer()

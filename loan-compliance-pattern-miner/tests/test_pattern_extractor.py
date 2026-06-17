#!/usr/bin/env python3
"""
Test pattern extractor
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.extractors.pattern_extractor import PatternExtractor

def test_pattern_extractor():
    extractor = PatternExtractor()
    
    # Test not_a_lender pattern
    text = "We are not a lender, we only provide loan matching services."
    result = extractor.extract(text, "not_a_lender")
    assert result == True
    
    text = "We are a direct lender offering personal loans."
    result = extractor.extract(text, "not_a_lender")
    assert result == False
    
    # Test no_guarantee pattern
    text = "Approval is not guaranteed and subject to credit check."
    result = extractor.extract(text, "no_guarantee")
    assert result == True
    
    text = "We guarantee approval for all applicants."
    result = extractor.extract(text, "no_guarantee")
    assert result == False
    
    # Test credit_check pattern
    text = "We may check your credit as part of the application process."
    result = extractor.extract(text, "credit_check")
    assert result == True
    
    text = "No credit check required for this loan."
    result = extractor.extract(text, "credit_check")
    assert result == False
    
    print("All pattern extractor tests passed!")

if __name__ == "__main__":
    test_pattern_extractor()

#!/usr/bin/env python3
"""
Test APR extractor
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.extractors.apr_extractor import APRExtractor

def test_apr_extractor():
    extractor = APRExtractor()
    
    # Test with text containing APR range
    text = "The APR ranges from 5.99% to 35.99%."
    found, apr_min, apr_max, apr_text = extractor.extract(text)
    assert found == True
    assert apr_min == 5.99
    assert apr_max == 35.99
    assert apr_text == "5.99% to 35.99%"
    
    # Test with text containing single APR
    text = "APR is 12.99%."
    found, apr_min, apr_max, apr_text = extractor.extract(text)
    assert found == True
    assert apr_min == 12.99
    assert apr_max == 12.99
    assert apr_text == "12.99%"
    
    # Test with text containing no APR
    text = "This is some text without APR information."
    found, apr_min, apr_max, apr_text = extractor.extract(text)
    assert found == False
    assert apr_min is None
    assert apr_max is None
    assert apr_text == ""
    
    print("All APR extractor tests passed!")

if __name__ == "__main__":
    test_apr_extractor()

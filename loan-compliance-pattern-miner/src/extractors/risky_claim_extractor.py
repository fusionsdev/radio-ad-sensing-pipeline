#!/usr/bin/env python3
"""
Risky claim extractor for finding risky financial claims
"""
from src.extractors.pattern_extractor import PatternExtractor

class RiskyClaimExtractor:
    def __init__(self):
        self.pattern_extractor = PatternExtractor()
    
    def extract(self, text):
        """Extract risky claims from text"""
        return self.pattern_extractor.extract(text, "risky_claims")

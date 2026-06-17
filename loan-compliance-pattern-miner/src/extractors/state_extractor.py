#!/usr/bin/env python3
"""
State extractor for finding state restriction information
"""
from src.extractors.pattern_extractor import PatternExtractor

class StateExtractor:
    def __init__(self):
        self.pattern_extractor = PatternExtractor()
    
    def extract(self, text):
        """Extract if state restriction information is found in text"""
        return self.pattern_extractor.extract(text, "state_restriction")

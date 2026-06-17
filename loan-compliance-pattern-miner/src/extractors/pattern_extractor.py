#!/usr/bin/env python3
"""
Pattern extractor for finding compliance disclaimers and patterns
"""
import yaml

class PatternExtractor:
    def __init__(self, config_path: str = "config/compliance_patterns.yaml"):
        self.patterns = self._load_patterns(config_path)
    
    def _load_patterns(self, config_path):
        """Load patterns from YAML config file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            # Return default patterns if file not found
            return {
                "not_a_lender": ["not a lender", "we are not a lender"],
                "no_guarantee": ["no guarantee", "approval not guaranteed"],
                "credit_check": ["credit check", "we may check your credit"],
                "state_restriction": ["not available in all states", "state restrictions"],
                "advertiser_disclosure": ["advertiser disclosure", "affiliate disclosure"],
                "risky_claims": ["guaranteed approval", "no credit check"]
            }
    
    def extract(self, text, pattern_category):
        """Extract if any pattern from the given category is found in text"""
        if pattern_category not in self.patterns:
            return False
        
        patterns = self.patterns[pattern_category]
        text_lower = text.lower()
        
        for pattern in patterns:
            if pattern.lower() in text_lower:
                return True
        
        return False

#!/usr/bin/env python3
"""
Text cleaner for normalizing extracted text
"""
class TextCleaner:
    def clean(self, text):
        """Clean and normalize text"""
        return text.strip() if text else ""

#!/usr/bin/env python3
"""
Markdown report generator for compliance findings
"""
import os
from typing import List, Dict
from datetime import datetime


class MarkdownReport:
    def generate(self, findings: List[Dict], filename: str):
        """
        Generate a markdown report from findings
        
        Args:
            findings: List of dictionaries containing finding data
            filename: Output markdown filename
        """
        # Ensure output directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            # Write header
            f.write("# Loan Compliance Pattern Analysis Report\n\n")
            f.write(f"**Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Total findings:** {len(findings)}\n\n")
            
            # Summary statistics
            f.write("## Summary Statistics\n\n")
            
            # Count by domain
            domain_counts = {}
            for finding in findings:
                domain = finding.get("domain", "unknown")
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
            
            f.write("### Findings by Domain\n\n")
            f.write("| Domain | Count |\n")
            f.write("|--------|-------|\n")
            for domain, count in sorted(domain_counts.items()):
                f.write(f"| {domain} | {count} |\n")
            f.write("\n")
            
            # Compliance completeness scores
            if findings:
                avg_completeness = sum(f.get("compliance_completeness_score", 0) for f in findings) / len(findings)
                f.write(f"**Average Compliance Completeness Score:** {avg_completeness:.1f}/100\n\n")
            
            # Policy risk scores
            if findings:
                avg_risk = sum(f.get("policy_risk_score", 0) for f in findings) / len(findings)
                f.write(f"**Average Policy Risk Score:** {avg_risk:.1f}/100\n\n")
            
            f.write("---\n")
            f.write("*Note: This tool identifies compliance signals, not legal conclusions.*\n")
        
        print(f"Generated markdown report: {filename}")

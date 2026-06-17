#!/usr/bin/env python3
"""
CSV exporter for compliance findings
"""
import csv
import os
from typing import List, Dict


class CSVExporter:
    def export(self, findings: List[Dict], filename: str):
        """
        Export findings to CSV file
        
        Args:
            findings: List of dictionaries containing finding data
            filename: Output CSV filename
        """
        # Ensure output directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Define the CSV columns
        columns = [
            "domain",
            "category",
            "url",
            "page_type",
            "apr_found",
            "apr_min",
            "apr_max",
            "apr_text",
            "not_lender_found",
            "no_guarantee_found",
            "credit_check_found",
            "state_restriction_found",
            "advertiser_disclosure_found",
            "risky_claims",
            "evidence_excerpt",
            "compliance_completeness_score",
            "policy_risk_score",
            "recommended_action",
            "crawled_at"
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            
            # Write header
            writer.writeheader()
            
            # Write data rows (empty for now since we don't have real findings)
            for finding in findings:
                # Create a row with only the columns we want
                row = {col: finding.get(col, '') for col in columns}
                writer.writerow(row)
        
        print(f"Exported {len(findings)} findings to {filename}")

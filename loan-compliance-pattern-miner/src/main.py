#!/usr/bin/env python3
"""
Loan Compliance Pattern Miner - Main CLI entry point
"""
import argparse
import sys
import os
from src.storage.db import Database
from src.reports.csv_exporter import CSVExporter
from src.reports.markdown_report import MarkdownReport


def crawl_command(args):
    """Handle the crawl command"""
    print(f"Starting crawl with config: {args.config}")
    # TODO: Implement actual crawl logic
    # For now, create some dummy data for testing
    db = Database()
    
    # Create a dummy finding for testing
    dummy_finding = {
        "domain": "example.com",
        "category": "direct_lender",
        "url": "https://example.com/terms",
        "page_type": "terms",
        "apr_found": True,
        "apr_min": 5.99,
        "apr_max": 35.99,
        "apr_text": "5.99% to 35.99%",
        "not_lender_found": False,
        "no_guarantee_found": True,
        "credit_check_found": True,
        "state_restriction_found": True,
        "advertiser_disclosure_found": True,
        "risky_claims": "",
        "evidence_excerpt": "The APR ranges from 5.99% to 35.99%. We check your credit and approval is not guaranteed.",
        "compliance_completeness_score": 85,
        "policy_risk_score": 20,
        "recommended_action": "REVIEW",
        "crawled_at": 1623456789.0
    }
    
    # Insert the dummy finding
    db.insert_finding(dummy_finding)
    print("Created dummy finding for testing.")


def report_command(args):
    """Handle the report command"""
    print(f"Generating {args.format} report...")
    
    # Initialize components
    db = Database()
    findings = db.get_all_findings()
    
    if args.format == "csv":
        # Ensure reports directory exists in project root
        os.makedirs("reports", exist_ok=True)
        exporter = CSVExporter()
        exporter.export(findings, "reports/compliance_report.csv")
        print(f"CSV report generated: reports/compliance_report.csv")
    elif args.format == "markdown":
        # Ensure reports directory exists in project root
        os.makedirs("reports", exist_ok=True)
        reporter = MarkdownReport()
        reporter.generate(findings, "reports/compliance_summary.md")
        print(f"Markdown report generated: reports/compliance_summary.md")
    else:
        print(f"Unknown format: {args.format}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Loan Compliance Pattern Miner")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Crawl command
    crawl_parser = subparsers.add_parser("crawl", help="Crawl domains for compliance patterns")
    crawl_parser.add_argument("--config", required=True, help="Path to seed domains YAML config")
    crawl_parser.set_defaults(func=crawl_command)
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate reports")
    report_parser.add_argument("--format", choices=["csv", "markdown"], required=True, help="Report format")
    report_parser.set_defaults(func=report_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()

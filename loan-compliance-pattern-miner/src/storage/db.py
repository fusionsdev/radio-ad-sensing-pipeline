#!/usr/bin/env python3
"""
Database module for storing findings using SQLite
"""
import sqlite3
import os
from typing import List, Dict


class Database:
    def __init__(self, db_path: str = "data/pipeline.db"):
        self.db_path = db_path
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create domains table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT UNIQUE NOT NULL,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create pages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_id INTEGER,
                url TEXT NOT NULL,
                page_type TEXT,
                title TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (domain_id) REFERENCES domains (id)
            )
        ''')
        
        # Create findings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id INTEGER,
                domain TEXT,
                category TEXT,
                url TEXT,
                page_type TEXT,
                apr_found BOOLEAN,
                apr_min REAL,
                apr_max REAL,
                apr_text TEXT,
                not_lender_found BOOLEAN,
                no_guarantee_found BOOLEAN,
                credit_check_found BOOLEAN,
                state_restriction_found BOOLEAN,
                advertiser_disclosure_found BOOLEAN,
                risky_claims TEXT,
                evidence_excerpt TEXT,
                compliance_completeness_score INTEGER,
                policy_risk_score INTEGER,
                recommended_action TEXT,
                crawled_at TIMESTAMP,
                FOREIGN KEY (page_id) REFERENCES pages (id)
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_findings_domain ON findings(domain)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_findings_page_id ON findings(page_id)
        ''')
        
        conn.commit()
        conn.close()
    
    def insert_finding(self, finding: Dict):
        """
        Insert a finding into the database
        
        Args:
            finding: Dictionary containing finding data
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # First, ensure domain exists
        domain = finding.get("domain")
        category = finding.get("category")
        
        cursor.execute(
            "INSERT OR IGNORE INTO domains (domain, category) VALUES (?, ?)",
            (domain, category)
        )
        
        # Get domain_id
        cursor.execute("SELECT id FROM domains WHERE domain = ?", (domain,))
        domain_result = cursor.fetchone()
        domain_id = domain_result[0] if domain_result else None
        
        # Insert page if not exists
        url = finding.get("url")
        page_type = finding.get("page_type")
        title = finding.get("title", "")  # We might need to extract this
        
        cursor.execute(
            "INSERT OR IGNORE INTO pages (domain_id, url, page_type, title) VALUES (?, ?, ?, ?)",
            (domain_id, url, page_type, title)
        )
        
        # Get page_id
        cursor.execute("SELECT id FROM pages WHERE url = ?", (url,))
        page_result = cursor.fetchone()
        page_id = page_result[0] if page_result else None
        
        # Insert finding
        query = '''
            INSERT INTO findings (
                page_id, domain, category, url, page_type,
                apr_found, apr_min, apr_max, apr_text,
                not_lender_found, no_guarantee_found, credit_check_found,
                state_restriction_found, advertiser_disclosure_found,
                risky_claims, evidence_excerpt,
                compliance_completeness_score, policy_risk_score,
                recommended_action, crawled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        values = (
            page_id,
            finding.get("domain"),
            finding.get("category"),
            finding.get("url"),
            finding.get("page_type"),
            finding.get("apr_found"),
            finding.get("apr_min"),
            finding.get("apr_max"),
            finding.get("apr_text"),
            finding.get("not_lender_found"),
            finding.get("no_guarantee_found"),
            finding.get("credit_check_found"),
            finding.get("state_restriction_found"),
            finding.get("advertiser_disclosure_found"),
            finding.get("risky_claims"),
            finding.get("evidence_excerpt"),
            finding.get("compliance_completeness_score"),
            finding.get("policy_risk_score"),
            finding.get("recommended_action"),
            finding.get("crawled_at")
        )
        
        cursor.execute(query, values)
        
        conn.commit()
        conn.close()
    
    def get_all_findings(self) -> List[Dict]:
        """
        Retrieve all findings from the database
        
        Returns:
            List of dictionaries containing finding data
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # This allows us to access columns by name
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT f.* FROM findings f
            ORDER BY f.crawled_at DESC
        ''')
        
        rows = cursor.fetchall()
        findings = []
        
        for row in rows:
            finding = dict(row)
            findings.append(finding)
        
        conn.close()
        return findings

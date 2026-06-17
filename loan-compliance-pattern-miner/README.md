# Loan Compliance Pattern Miner

A Python tool for crawling loan/financing websites and extracting common compliance patterns.

## Features

- Crawls seed domains for compliance-related pages
- Extracts APR disclosures using pattern matching
- Identifies compliance disclaimers (not-a-lender, no-guarantee, etc.)
- Detects risky financial claims
- Calculates compliance completeness and policy risk scores
- Exports results to CSV and markdown reports
- Polite crawling with delay between requests, max pages per domain, timeout, and retries

## Tech Stack

- Python 3.11+
- SQLite
- YAML config
- CSV export
- Markdown report
- Requests for fetching
- BeautifulSoup for parsing
- Optional Playwright fallback for JavaScript-rendered pages
- pytest for testing

## Project Structure

```
loan-compliance-pattern-miner/
├── config/
│   ├── seed_domains.yaml
│   └── compliance_patterns.yaml
├── src/
│   ├── main.py
│   ├── collectors/
│   │   └── web_collector.py
│   ├── extractors/
│   │   ├── apr_extractor.py
│   │   ├── pattern_extractor.py
│   │   ├── state_extractor.py
│   │   └── risky_claim_extractor.py
│   ├── normalizers/
│   │   ├── url_classifier.py
│   │   └── text_cleaner.py
│   ├── scoring/
│   │   └── compliance_score.py
│   ├── storage/
│   │   └── db.py
│   └── reports/
│       ├── csv_exporter.py
│       └── markdown_report.py
├── tests/
├── data/
├── reports/
├── README.md
└── requirements.txt
```

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Crawl Domains

```bash
python -m src.main crawl --config config/seed_domains.yaml
```

### Generate Reports

```bash
# Generate CSV report
python -m src.main report --format csv

# Generate markdown report
python -m src.main report --format markdown
```

## Configuration

### seed_domains.yaml

```yaml
domains:
  - example-loan-site.com
  - another-lender.net
```

### compliance_patterns.yaml

```yaml
not_a_lender:
  - "not a lender"
  - "we are not a lender"
  - "does not make loans"

no_guarantee:
  - "no guarantee"
  - "approval not guaranteed"

credit_check:
  - "credit check"
  - "we may check your credit"

state_restriction:
  - "not available in all states"
  - "state restrictions"

advertiser_disclosure:
  - "advertiser disclosure"
  - "affiliate disclosure"

risky_claims:
  - "guaranteed approval"
  - "100% approval"
  - "no credit check"
  - "instant approval"
```

## Database Schema

The tool uses SQLite to store findings with the following tables:

- **domains**: Stores domain information
- **pages**: Stores crawled pages
- **findings**: Stores compliance findings extracted from pages

## Testing

Run tests with pytest:

```bash
pytest
```

## Disclaimer

This tool identifies compliance signals and patterns for informational purposes only. It does not provide legal advice or legal conclusions. Users should consult with legal professionals for compliance determinations.


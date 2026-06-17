"""Conservative landing page text importer for novelty discovery."""

from __future__ import annotations

import csv
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from worker.discovery_import import insert_raw_discovery_item
from worker.novelty_engine import (
    CandidateInput,
    NoveltyConfig,
    NoveltyEvaluation,
    evaluate_candidate,
    load_novelty_config,
    normalize_candidate_text,
    process_candidate,
)

SOURCE_TYPE = "landing_page"
IMPORT_BATCH_ID = "landing_pages_import"
USER_AGENT = "RadioAdPipeline-LandingImporter/1.0 (+manual-review; conservative)"
DEFAULT_TIMEOUT_SECONDS = 15.0

BOILERPLATE_PHRASES = frozenset(
    {
        "apply now",
        "learn more",
        "contact us",
        "privacy policy",
        "terms of service",
        "cookie policy",
        "home",
        "about us",
        "click here",
        "read more",
        "get started",
        "sign in",
        "log in",
        "subscribe",
        "menu",
    }
)

FINANCING_SIGNAL = re.compile(
    r"\b("
    r"payment|payments|pay|finance|financing|monthly|credit|qualif|upfront|"
    r"bill|procedure|plan|treatment|approval|installment|care|vet|dental|"
    r"surgery|loan|split|afford|eligible|interest|deposit|down payment|"
    r"prequal|pre-qual|without affecting"
    r")\b",
    re.IGNORECASE,
)

FetchFn = Callable[[str, float], tuple[int | None, str]]


@dataclass(frozen=True)
class LandingPageSpec:
    url: str
    vertical: str
    source_confidence: float
    notes: str | None = None


@dataclass(frozen=True)
class PageTextExtract:
    url: str
    title: str
    meta_description: str
    headings: tuple[str, ...]
    cta_buttons: tuple[str, ...]
    form_labels: tuple[str, ...]
    faq_items: tuple[str, ...]
    paragraphs: tuple[str, ...]
    disclosures: tuple[str, ...]


@dataclass(frozen=True)
class ExtractedPhrase:
    candidate_text: str
    candidate_type: str
    evidence_text: str
    source_url: str


@dataclass(frozen=True)
class LandingPageCandidateResult:
    url: str
    vertical: str
    candidate_text: str
    candidate_type: str
    evidence_text: str
    novelty_status: str
    novelty_score: float
    opportunity_score: float
    report_eligible: bool
    suppression_reason: str | None


@dataclass
class LandingPageImportReport:
    input_path: Path
    pages_attempted: int = 0
    pages_processed: int = 0
    candidates_extracted: int = 0
    candidates_processed: int = 0
    report_eligible: int = 0
    suppressed: int = 0
    errors: list[str] = field(default_factory=list)
    records: list[LandingPageCandidateResult] = field(default_factory=list)

    @property
    def top_opportunities(self) -> list[LandingPageCandidateResult]:
        eligible = [row for row in self.records if row.report_eligible]
        return sorted(
            eligible,
            key=lambda row: (row.opportunity_score, row.novelty_score),
            reverse=True,
        )[:10]

    def as_dict(self) -> dict[str, Any]:
        return {
            "import_source": SOURCE_TYPE,
            "batch_id": IMPORT_BATCH_ID,
            "input_path": str(self.input_path),
            "pages_attempted": self.pages_attempted,
            "pages_processed": self.pages_processed,
            "candidates_extracted": self.candidates_extracted,
            "candidates_processed": self.candidates_processed,
            "report_eligible": self.report_eligible,
            "suppressed": self.suppressed,
            "errors": list(self.errors),
            "top_opportunities": [
                {
                    "url": row.url,
                    "candidate_text": row.candidate_text,
                    "novelty_score": row.novelty_score,
                    "opportunity_score": row.opportunity_score,
                }
                for row in self.top_opportunities
            ],
        }


class _MarketingTextExtractor(HTMLParser):
    _SKIP_ROOTS = frozenset({"nav", "footer", "script", "style", "noscript", "svg"})

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self._in_title = False
        self._skip_depth = 0
        self._current_tag: str | None = None
        self._buffer: list[str] = []
        self.headings: list[str] = []
        self.cta_buttons: list[str] = []
        self.form_labels: list[str] = []
        self.faq_items: list[str] = []
        self.paragraphs: list[str] = []
        self.disclosures: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): (value or "") for key, value in attrs}
        if tag in self._SKIP_ROOTS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = True
            self._buffer = []
        elif tag == "meta" and attrs_dict.get("name", "").lower() == "description":
            content = attrs_dict.get("content", "").strip()
            if content:
                self.meta_description = content
        elif tag in {"h1", "h2", "h3"}:
            self._current_tag = tag
            self._buffer = []
        elif tag == "button":
            self._current_tag = "cta"
            self._buffer = []
        elif tag == "a" and self._looks_like_cta(attrs_dict):
            self._current_tag = "cta"
            self._buffer = []
        elif tag == "label":
            self._current_tag = "label"
            self._buffer = []
        elif tag in {"p", "li"}:
            self._current_tag = tag
            self._buffer = []
        elif tag == "summary":
            self._current_tag = "summary"
            self._buffer = []
        elif tag == "small":
            self._current_tag = "small"
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_ROOTS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "title" and self._in_title:
            self.title = _clean_whitespace("".join(self._buffer))
            self._in_title = False
            self._buffer = []
            return
        closes = tag == self._current_tag or (
            self._current_tag == "cta" and tag in {"button", "a"}
        )
        if self._current_tag and closes:
            text = _clean_whitespace("".join(self._buffer))
            if text:
                if self._current_tag in {"h1", "h2", "h3"}:
                    self.headings.append(text)
                elif self._current_tag == "cta":
                    self.cta_buttons.append(text)
                elif self._current_tag == "label":
                    self.form_labels.append(text)
                elif self._current_tag == "summary":
                    self.faq_items.append(text)
                elif self._current_tag in {"p", "li"}:
                    self.paragraphs.append(text)
                elif self._current_tag == "small":
                    self.disclosures.append(text)
            self._current_tag = None
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title or self._current_tag:
            self._buffer.append(data)

    @staticmethod
    def _looks_like_cta(attrs: dict[str, str]) -> bool:
        classes = attrs.get("class", "").lower()
        role = attrs.get("role", "").lower()
        return "btn" in classes or "button" in classes or role == "button"


def _clean_whitespace(text: str) -> str:
    return " ".join(text.split()).strip()


def load_landing_pages_json(path: Path) -> tuple[list[LandingPageSpec], list[str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [f"Invalid JSON: {exc}"]
    if not isinstance(raw, list):
        return [], ["Input JSON must be a top-level array"]
    specs: list[LandingPageSpec] = []
    errors: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"Record {index}: must be an object")
            continue
        url = item.get("url")
        vertical = item.get("vertical")
        confidence = item.get("source_confidence")
        if not url or not vertical or confidence in (None, ""):
            errors.append(f"Record {index}: url, vertical, and source_confidence are required")
            continue
        try:
            conf_value = float(confidence)
        except (TypeError, ValueError):
            errors.append(f"Record {index}: source_confidence must be numeric")
            continue
        specs.append(
            LandingPageSpec(
                url=str(url).strip(),
                vertical=str(vertical).strip(),
                source_confidence=conf_value,
                notes=str(item["notes"]).strip() if item.get("notes") else None,
            )
        )
    return specs, errors


def default_fetch(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> tuple[int | None, str]:
    """Fetch a landing page with a conservative timeout and explicit user agent."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read()
            return int(status), body.decode(charset, errors="replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise RuntimeError(f"fetch failed: {exc.reason}") from exc


def extract_visible_text(html: str, *, url: str = "") -> PageTextExtract:
    parser = _MarketingTextExtractor()
    parser.feed(html)
    parser.close()
    return PageTextExtract(
        url=url,
        title=parser.title,
        meta_description=parser.meta_description,
        headings=tuple(parser.headings),
        cta_buttons=tuple(parser.cta_buttons),
        form_labels=tuple(parser.form_labels),
        faq_items=tuple(parser.faq_items),
        paragraphs=tuple(parser.paragraphs),
        disclosures=tuple(parser.disclosures),
    )


def is_boilerplate_phrase(text: str) -> bool:
    normalized = normalize_candidate_text(text)
    if not normalized:
        return True
    if normalized in BOILERPLATE_PHRASES:
        return True
    if len(normalized) < 8:
        return True
    return False


def _classify_phrase(text: str, *, origin: str) -> str:
    lowered = text.lower()
    if origin in {"cta", "meta"}:
        return "offer_angle"
    if "?" in text or any(word in lowered for word in ("afford", "unexpected", "emergency", "help")):
        return "pain_phrase"
    if origin in {"heading", "faq", "paragraph"}:
        return "use_case"
    if origin == "label":
        return "offer_angle"
    return "keyword"


def _phrase_priority(text: str, *, origin: str) -> float:
    score = 0.0
    words = len(normalize_candidate_text(text).split())
    score += min(words, 8) * 2.0
    if FINANCING_SIGNAL.search(text):
        score += 10.0
    if origin in {"heading", "meta", "faq"}:
        score += 4.0
    if origin == "cta" and FINANCING_SIGNAL.search(text):
        score += 6.0
    return score


def extract_candidate_phrases(page: PageTextExtract) -> list[ExtractedPhrase]:
    """Extract marketing phrases likely to represent novel financing angles."""
    candidates: list[tuple[float, ExtractedPhrase]] = []
    seen: set[str] = set()

    def add(text: str, *, origin: str, evidence: str) -> None:
        cleaned = _clean_whitespace(text)
        if is_boilerplate_phrase(cleaned):
            return
        if not FINANCING_SIGNAL.search(cleaned):
            return
        normalized = normalize_candidate_text(cleaned)
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append(
            (
                _phrase_priority(cleaned, origin=origin),
                ExtractedPhrase(
                    candidate_text=cleaned,
                    candidate_type=_classify_phrase(cleaned, origin=origin),
                    evidence_text=evidence,
                    source_url=page.url,
                ),
            )
        )

    if page.title:
        add(page.title, origin="heading", evidence=f"title: {page.title}")
    if page.meta_description:
        add(page.meta_description, origin="meta", evidence=f"meta description: {page.meta_description}")
    for heading in page.headings:
        add(heading, origin="heading", evidence=f"heading: {heading}")
    for button in page.cta_buttons:
        add(button, origin="cta", evidence=f"cta: {button}")
    for label in page.form_labels:
        add(label, origin="label", evidence=f"form label: {label}")
    for faq in page.faq_items:
        add(faq, origin="faq", evidence=f"faq: {faq}")
    for paragraph in page.paragraphs:
        if 20 <= len(paragraph) <= 320:
            add(paragraph, origin="paragraph", evidence=f"paragraph: {paragraph[:240]}")
    for disclosure in page.disclosures:
        if FINANCING_SIGNAL.search(disclosure):
            add(disclosure, origin="paragraph", evidence=f"disclosure: {disclosure[:240]}")

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [phrase for _, phrase in candidates]


def _evaluation_to_result(
    *,
    spec: LandingPageSpec,
    phrase: ExtractedPhrase,
    evaluation: NoveltyEvaluation,
) -> LandingPageCandidateResult:
    return LandingPageCandidateResult(
        url=spec.url,
        vertical=spec.vertical,
        candidate_text=phrase.candidate_text,
        candidate_type=phrase.candidate_type,
        evidence_text=phrase.evidence_text,
        novelty_status=evaluation.novelty_status,
        novelty_score=evaluation.novelty_score,
        opportunity_score=evaluation.opportunity_score,
        report_eligible=evaluation.report_eligible,
        suppression_reason=evaluation.report_suppressed_reason,
    )


def import_landing_pages(
    db_path: str | Path,
    specs: list[LandingPageSpec],
    *,
    dry_run: bool = False,
    max_pages: int = 10,
    max_candidates_per_page: int = 50,
    fetch_fn: FetchFn | None = None,
    config: NoveltyConfig | None = None,
) -> LandingPageImportReport:
    cfg = config or load_novelty_config()
    fetch = fetch_fn or default_fetch
    report = LandingPageImportReport(input_path=Path("inline"))
    report.pages_attempted = min(len(specs), max_pages)

    for spec in specs[:max_pages]:
        try:
            status, html = fetch(spec.url, DEFAULT_TIMEOUT_SECONDS)
            if status is None or status >= 400 or not html.strip():
                report.errors.append(f"{spec.url}: HTTP {status or 'error'} — skipped")
                continue

            page = extract_visible_text(html, url=spec.url)
            phrases = extract_candidate_phrases(page)[:max_candidates_per_page]
            report.pages_processed += 1
            report.candidates_extracted += len(phrases)

            if dry_run:
                for phrase in phrases:
                    evaluation = evaluate_candidate(
                        CandidateInput(
                            candidate_text=phrase.candidate_text,
                            candidate_type=phrase.candidate_type,
                            vertical=spec.vertical,
                            source_type=SOURCE_TYPE,
                            source_url=spec.url,
                            evidence_text=phrase.evidence_text,
                            source_confidence=spec.source_confidence,
                        ),
                        cfg,
                    )
                    report.records.append(
                        _evaluation_to_result(spec=spec, phrase=phrase, evaluation=evaluation)
                    )
                    report.candidates_processed += 1
                    if evaluation.report_eligible:
                        report.report_eligible += 1
                    else:
                        report.suppressed += 1
                continue

            raw_record = {
                "batch_id": IMPORT_BATCH_ID,
                "source_type": SOURCE_TYPE,
                "source_url": spec.url,
                "url": spec.url,
                "vertical": spec.vertical,
                "source_confidence": spec.source_confidence,
                "notes": spec.notes,
                "title": page.title,
                "meta_description": page.meta_description,
                "evidence_text": page.meta_description or page.title,
                "candidate_text": page.title,
                "extracted_phrase_count": len(phrases),
            }
            raw_item_id = insert_raw_discovery_item(db_path, raw_record)

            for phrase in phrases:
                candidate = CandidateInput(
                    candidate_text=phrase.candidate_text,
                    candidate_type=phrase.candidate_type,
                    vertical=spec.vertical,
                    source_type=SOURCE_TYPE,
                    source_url=spec.url,
                    evidence_text=phrase.evidence_text,
                    source_confidence=spec.source_confidence,
                    raw_item_id=raw_item_id,
                )
                _, evaluation = process_candidate(db_path, candidate, config=cfg)
                report.records.append(
                    _evaluation_to_result(spec=spec, phrase=phrase, evaluation=evaluation)
                )
                report.candidates_processed += 1
                if evaluation.report_eligible:
                    report.report_eligible += 1
                else:
                    report.suppressed += 1
        except Exception as exc:  # pragma: no cover - defensive for CLI
            report.errors.append(f"{spec.url}: {exc}")

    return report


def import_landing_pages_file(
    db_path: str | Path,
    input_path: Path,
    *,
    dry_run: bool = False,
    max_pages: int = 10,
    max_candidates_per_page: int = 50,
    fetch_fn: FetchFn | None = None,
    config: NoveltyConfig | None = None,
) -> LandingPageImportReport:
    specs, errors = load_landing_pages_json(input_path)
    report = import_landing_pages(
        db_path,
        specs,
        dry_run=dry_run,
        max_pages=max_pages,
        max_candidates_per_page=max_candidates_per_page,
        fetch_fn=fetch_fn,
        config=config,
    )
    report.input_path = input_path
    report.errors = errors + report.errors
    report.pages_attempted = min(len(specs), max_pages)
    return report


def write_landing_pages_csv(report: LandingPageImportReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "url",
        "candidate_text",
        "candidate_type",
        "vertical",
        "novelty_status",
        "novelty_score",
        "opportunity_score",
        "report_eligible",
        "suppression_reason",
        "evidence_text",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report.records:
            writer.writerow(
                {
                    "url": row.url,
                    "candidate_text": row.candidate_text,
                    "candidate_type": row.candidate_type,
                    "vertical": row.vertical,
                    "novelty_status": row.novelty_status,
                    "novelty_score": f"{row.novelty_score:.2f}",
                    "opportunity_score": f"{row.opportunity_score:.2f}",
                    "report_eligible": "yes" if row.report_eligible else "no",
                    "suppression_reason": row.suppression_reason or "",
                    "evidence_text": row.evidence_text,
                }
            )
    return output_path


def write_landing_pages_meta(report: LandingPageImportReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    return output_path


def format_landing_page_summary(report: LandingPageImportReport) -> str:
    lines = [
        "=== Landing page import ===",
        f"Input: {report.input_path}",
        f"Pages attempted:     {report.pages_attempted}",
        f"Pages processed:     {report.pages_processed}",
        f"Candidates extracted:{report.candidates_extracted}",
        f"Candidates processed:{report.candidates_processed}",
        f"Report eligible:     {report.report_eligible}",
        f"Suppressed:          {report.suppressed}",
        f"Errors:              {len(report.errors)}",
    ]
    if report.top_opportunities:
        lines.extend(["", "Top opportunities:"])
        for row in report.top_opportunities[:10]:
            lines.append(
                f"  - {row.candidate_text} "
                f"(novelty={row.novelty_score:.0f}, opp={row.opportunity_score:.0f})"
            )
    if report.errors:
        lines.extend(["", "Errors:"])
        for error in report.errors:
            lines.append(f"  - {error}")
    return "\n".join(lines)

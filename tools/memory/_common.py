"""Shared utilities for project-memory loggers and harness."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORY_ROOT = PROJECT_ROOT / "project-memory"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
BASELINES_DIR = Path(__file__).resolve().parent / "baselines"

DECISIONS_DIR = MEMORY_ROOT / "Decisions"
INCIDENTS_DIR = MEMORY_ROOT / "Incidents"
STATIONS_DIR = MEMORY_ROOT / "Stations"
RUNBOOKS_DIR = MEMORY_ROOT / "Runbooks"

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
SECTION_EMPTY_RE = re.compile(r"^##\s+(\w[\w\s]*)\s*\n\s*(?:\n|$)", re.MULTILINE)

BEHAVIOR_COMPONENTS: dict[str, list[str]] = {
    "classifier": ["scripts/loan_classifier.py"],
    "station_policy": [
        "scripts/station_rotation.py",
        "config/stations.yaml",
        "tools/harness/cases/station_rotation_cases.yaml",
    ],
    "dashboard_routing": [
        "dashboard/main.py",
        "dashboard/routes/radiosense.py",
        "dashboard/routes/harvest.py",
        "dashboard/routes/system.py",
        "dashboard/routes/hermes.py",
        "dashboard/routes/novelty.py",
        "dashboard/routes/memory.py",
    ],
}


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_str() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%d")


def slugify(title: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "untitled"


def load_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing template: {path}")
    return path.read_text(encoding="utf-8")


def render_template(name: str, **fields: str) -> str:
    content = load_template(name)
    for key, value in fields.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component_fingerprint(files: list[str]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(files):
        path = PROJECT_ROOT / rel
        digest.update(rel.encode())
        digest.update(file_hash(path).encode())
    return digest.hexdigest()


def find_markdown_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(p for p in directory.rglob("*.md") if p.is_file())


def parse_wikilinks(text: str) -> list[str]:
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]


def resolve_wikilink(target: str, source: Path) -> Path | None:
    """Resolve Obsidian wikilink to vault markdown path."""
    candidates: list[Path] = []
    name = target.strip()
    if "/" in name:
        candidates.append(MEMORY_ROOT / f"{name}.md")
    else:
        candidates.append(source.parent / f"{name}.md")
        candidates.append(MEMORY_ROOT / f"{name}.md")
        for sub in ("Decisions", "Runbooks", "Stations", "Incidents", "Reports"):
            candidates.append(MEMORY_ROOT / sub / f"{name}.md")
    for path in candidates:
        if path.exists():
            return path
    return None


def empty_sections(text: str) -> list[str]:
    """Return section headings with no body content before the next heading."""
    empty: list[str] = []
    parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    for part in parts:
        if not part.startswith("## "):
            continue
        lines = part.strip().splitlines()
        if len(lines) <= 1:
            empty.append(lines[0].lstrip("# ").strip())
            continue
        body = "\n".join(lines[1:]).strip()
        if not body or body in {"(none)", "TBD", "—", "-"}:
            empty.append(lines[0].lstrip("# ").strip())
    return empty


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
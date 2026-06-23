"""Capture operational incidents in project-memory/Incidents/."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.memory._common import INCIDENTS_DIR, ensure_dir, render_template, slugify, today_str


def log_incident(
    title: str,
    *,
    symptoms: str,
    root_cause: str = "",
    resolution: str = "",
    prevention: str = "",
    related_components: list[str] | None = None,
    date: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Write a dated incident file and return its path."""
    ensure_dir(INCIDENTS_DIR)
    day = date or today_str()
    slug = slugify(title)
    if not slug.startswith("incident"):
        slug = f"incident-{slug}" if "incident" not in slug else slug
    filename = f"{day}-{slug}.md"
    path = INCIDENTS_DIR / filename
    if path.exists() and not overwrite:
        raise FileExistsError(f"Incident already exists: {path}")

    components_text = "\n".join(f"- {c}" for c in (related_components or [])) or "(none)"
    body = render_template(
        "incident.md",
        date=day,
        symptoms=symptoms.strip(),
        root_cause=root_cause.strip() or "Under investigation",
        resolution=resolution.strip() or "Pending",
        prevention=prevention.strip() or "TBD",
        related_components=components_text,
    )
    path.write_text(body, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Log an incident to project-memory/Incidents/")
    parser.add_argument("title", help="Short incident title")
    parser.add_argument("--symptoms", required=True, help="Observed behavior")
    parser.add_argument("--root-cause", default="", help="Underlying issue")
    parser.add_argument("--resolution", default="", help="Fix applied")
    parser.add_argument("--prevention", default="", help="Future prevention")
    parser.add_argument("--components", nargs="*", default=[], help="Affected services")
    parser.add_argument("--date", default=None, help="Override date (YYYY-MM-DD)")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    path = log_incident(
        args.title,
        symptoms=args.symptoms,
        root_cause=args.root_cause,
        resolution=args.resolution,
        prevention=args.prevention,
        related_components=args.components,
        date=args.date,
        overwrite=args.overwrite,
    )
    print(path.relative_to(path.parents[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
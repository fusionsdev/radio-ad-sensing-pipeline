"""Create decision records in project-memory/Decisions/."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.memory._common import DECISIONS_DIR, ensure_dir, render_template, slugify, today_str
from tools.memory.behavior import sync_baseline_after_documented_changes


def log_decision(
    title: str,
    *,
    context: str,
    decision: str,
    impact: str = "",
    rollback: str = "",
    related_files: list[str] | None = None,
    date: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Write a dated decision file and return its path."""
    ensure_dir(DECISIONS_DIR)
    day = date or today_str()
    filename = f"{day}-{slugify(title)}.md"
    path = DECISIONS_DIR / filename
    if path.exists() and not overwrite:
        raise FileExistsError(f"Decision already exists: {path}")

    files_text = "\n".join(f"- `{f}`" for f in (related_files or [])) or "(none)"
    body = render_template(
        "decision.md",
        date=day,
        context=context.strip(),
        decision=decision.strip(),
        impact=impact.strip() or "TBD",
        rollback=rollback.strip() or "Revert related files to prior commit.",
        related_files=files_text,
    )
    path.write_text(body, encoding="utf-8")
    sync_baseline_after_documented_changes()
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Log a project decision to project-memory/Decisions/")
    parser.add_argument("title", help="Short decision title")
    parser.add_argument("--context", required=True, help="Why the change was required")
    parser.add_argument("--decision", required=True, help="What was changed")
    parser.add_argument("--impact", default="", help="Expected effect")
    parser.add_argument("--rollback", default="", help="How to revert")
    parser.add_argument("--related-files", nargs="*", default=[], help="Files involved")
    parser.add_argument("--date", default=None, help="Override date (YYYY-MM-DD)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing file")
    args = parser.parse_args(argv)

    path = log_decision(
        args.title,
        context=args.context,
        decision=args.decision,
        impact=args.impact,
        rollback=args.rollback,
        related_files=args.related_files,
        date=args.date,
        overwrite=args.overwrite,
    )
    print(path.relative_to(path.parents[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
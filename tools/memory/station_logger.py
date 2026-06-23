"""Track station lifecycle in project-memory/Stations/."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from tools.memory._common import STATIONS_DIR, ensure_dir, render_template, today_str

VALID_STATUSES = frozenset({"keep", "watch", "pause", "rotate_out", "replace"})


def _station_filename(call_sign: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9]", "", call_sign).upper()
    return f"{clean}.md"


def _parse_station_file(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = ""
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                sections[current] = "\n".join(lines).strip()
            current = line[3:].strip().lower()
            lines = []
        else:
            lines.append(line)
    if current:
        sections[current] = "\n".join(lines).strip()
    return sections


def log_station_change(
    call_sign: str,
    status: str,
    *,
    reasoning: str = "",
    advertisers: list[str] | None = None,
    metrics: str = "",
    date: str | None = None,
) -> Path:
    """Append a status change to the station memory file."""
    status_norm = status.lower().replace(" ", "_")
    if status_norm not in VALID_STATUSES:
        raise ValueError(f"Invalid status {status!r}; expected one of {sorted(VALID_STATUSES)}")

    ensure_dir(STATIONS_DIR)
    path = STATIONS_DIR / _station_filename(call_sign)
    day = date or today_str()
    entry = f"- **{day}** — {status_norm}: {reasoning.strip() or '(no reason given)'}"

    if path.exists():
        sections = _parse_station_file(path.read_text(encoding="utf-8"))
        history = sections.get("history", "")
        history = f"{history}\n{entry}".strip() if history else entry
        body = render_template(
            "station.md",
            call_sign=call_sign.upper(),
            status=status_norm,
            history=history,
            reasoning=reasoning.strip() or sections.get("reasoning", "TBD"),
            advertisers=sections.get("detected advertisers", "(none)"),
            metrics=metrics.strip() or sections.get("performance metrics", "(none)"),
        )
    else:
        adv_text = "\n".join(f"- {a}" for a in (advertisers or [])) or "(none)"
        body = render_template(
            "station.md",
            call_sign=call_sign.upper(),
            status=status_norm,
            history=entry,
            reasoning=reasoning.strip() or "Initial station record.",
            advertisers=adv_text,
            metrics=metrics.strip() or "(none)",
        )

    path.write_text(body, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Log station lifecycle change")
    parser.add_argument("call_sign", help="Station call sign (e.g. WBAP)")
    parser.add_argument("status", choices=sorted(VALID_STATUSES), help="New status")
    parser.add_argument("--reasoning", default="", help="Operational notes")
    parser.add_argument("--advertisers", nargs="*", default=[])
    parser.add_argument("--metrics", default="")
    parser.add_argument("--date", default=None)
    args = parser.parse_args(argv)

    path = log_station_change(
        args.call_sign,
        args.status,
        reasoning=args.reasoning,
        advertisers=args.advertisers,
        metrics=args.metrics,
        date=args.date,
    )
    print(path.relative_to(path.parents[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
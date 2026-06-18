"""Vertical keyword config, hit classification, and report eligibility."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from shared.models import LoanKeywordEntry, VerticalConfig, VerticalKeywordsFile

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_VERTICAL_CONFIG = CONFIG_DIR / "vertical_keywords.yaml"


@dataclass(frozen=True)
class VerticalHitSummary:
    vertical: str
    label: str
    tier: str
    vertical_hit_count: int
    station_count: int
    latest_seen_at: float | None
    source_keywords: tuple[str, ...]
    confidence: float
    report_eligible: bool
    no_hit_ok: bool = False


def _normalize_vertical_data(data: object) -> object:
    if not isinstance(data, dict):
        return data
    verticals = data.get("verticals")
    if not isinstance(verticals, dict):
        return data
    normalized: dict[str, object] = {}
    for key, vertical in verticals.items():
        if not isinstance(vertical, dict):
            normalized[key] = vertical
            continue
        raw_keywords = vertical.get("keywords", [])
        kw_list: list[object] = []
        if isinstance(raw_keywords, list):
            for item in raw_keywords:
                if isinstance(item, str):
                    kw_list.append({"phrase": item.strip(), "confidence": 0.7})
                else:
                    kw_list.append(item)
        normalized[key] = {**vertical, "keywords": kw_list}
    return {**data, "verticals": normalized}


def load_vertical_keywords(path: Path | None = None) -> VerticalKeywordsFile:
    config_path = path or DEFAULT_VERTICAL_CONFIG
    if not config_path.is_file():
        return VerticalKeywordsFile(verticals={})
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return VerticalKeywordsFile.model_validate(_normalize_vertical_data(data))


def flatten_vertical_keywords(config: VerticalKeywordsFile | None = None) -> list[LoanKeywordEntry]:
    """All keyword phrases across verticals for transcript scanning."""
    cfg = config or load_vertical_keywords()
    entries: list[LoanKeywordEntry] = []
    seen: set[str] = set()
    for vertical in cfg.verticals.values():
        for entry in vertical.keywords:
            phrase = entry.phrase.strip()
            if phrase and phrase.lower() not in seen:
                seen.add(phrase.lower())
                entries.append(entry)
    return entries


def keyword_to_vertical_map(config: VerticalKeywordsFile | None = None) -> dict[str, str]:
    cfg = config or load_vertical_keywords()
    mapping: dict[str, str] = {}
    for vertical_id, vertical in cfg.verticals.items():
        for entry in vertical.keywords:
            mapping[entry.phrase.lower()] = vertical_id
    return mapping


def _vertical_config(vertical_id: str, config: VerticalKeywordsFile) -> VerticalConfig:
    return config.verticals[vertical_id]


def _compute_report_eligible(
    *,
    vertical_id: str,
    hit_count: int,
    confidence: float,
    config: VerticalKeywordsFile,
) -> bool:
    if hit_count <= 0:
        return False
    vertical = _vertical_config(vertical_id, config)
    min_hits = vertical.report_eligible_min_hits
    if min_hits is not None and hit_count < min_hits:
        return False
    if vertical.report_eligible is False:
        return hit_count > 0
    if vertical.report_eligible is True:
        return True
    return hit_count > 0


def _apply_confidence_cap(
    *,
    vertical_id: str,
    hit_count: int,
    confidence: float,
    config: VerticalKeywordsFile,
) -> float:
    vertical = _vertical_config(vertical_id, config)
    cap = vertical.confidence_cap_sparse
    min_hits = vertical.report_eligible_min_hits
    if cap is not None and min_hits is not None and hit_count < min_hits:
        return min(confidence, cap)
    return confidence


def classify_vertical_hits(
    rows: list[sqlite3.Row] | list[dict],
    *,
    config: VerticalKeywordsFile | None = None,
    now: float | None = None,
) -> list[VerticalHitSummary]:
    """Aggregate raw keyword_hits rows into per-vertical summaries."""
    cfg = config or load_vertical_keywords()
    mapping = keyword_to_vertical_map(cfg)
    _now = now if now is not None else time.time()

    buckets: dict[str, dict] = {}
    for raw in rows:
        row = dict(raw)
        keyword = str(row["keyword"]).lower()
        vertical_id = mapping.get(keyword)
        if vertical_id is None:
            continue
        bucket = buckets.setdefault(
            vertical_id,
            {
                "hit_count": 0,
                "stations": set(),
                "keywords": set(),
                "confidences": [],
                "latest_ts": None,
            },
        )
        bucket["hit_count"] += int(row.get("hits") or row.get("hit_count") or 1)
        station = row.get("station_id") or row.get("station_name")
        if station is not None:
            bucket["stations"].add(station)
        bucket["keywords"].add(str(row["keyword"]))
        for entry in cfg.verticals[vertical_id].keywords:
            if entry.phrase.lower() == keyword:
                bucket["confidences"].append(entry.confidence)
                break
        hit_ts = row.get("hit_ts") or row.get("latest_seen_at")
        if hit_ts is not None:
            ts = float(hit_ts)
            if bucket["latest_ts"] is None or ts > bucket["latest_ts"]:
                bucket["latest_ts"] = ts

    summaries: list[VerticalHitSummary] = []
    for vertical_id, vertical in cfg.verticals.items():
        bucket = buckets.get(vertical_id)
        hit_count = int(bucket["hit_count"]) if bucket else 0
        station_count = len(bucket["stations"]) if bucket else 0
        source_keywords = tuple(sorted(bucket["keywords"])) if bucket else ()
        latest = bucket["latest_ts"] if bucket else None
        if bucket and bucket["confidences"]:
            confidence = max(bucket["confidences"])
        elif hit_count > 0:
            confidence = 0.7
        else:
            confidence = 0.0
        confidence = _apply_confidence_cap(
            vertical_id=vertical_id,
            hit_count=hit_count,
            confidence=confidence,
            config=cfg,
        )
        report_eligible = _compute_report_eligible(
            vertical_id=vertical_id,
            hit_count=hit_count,
            confidence=confidence,
            config=cfg,
        )
        summaries.append(
            VerticalHitSummary(
                vertical=vertical_id,
                label=vertical.label,
                tier=vertical.tier,
                vertical_hit_count=hit_count,
                station_count=station_count,
                latest_seen_at=latest,
                source_keywords=source_keywords,
                confidence=round(confidence, 3),
                report_eligible=report_eligible,
                no_hit_ok=bool(vertical.no_hit_ok),
            )
        )

    summaries.sort(
        key=lambda item: (
            {"hot": 0, "watchlist": 1, "active": 2}.get(item.tier, 3),
            -item.vertical_hit_count,
            item.label,
        )
    )
    return summaries


def fetch_vertical_summaries_from_db(
    conn: sqlite3.Connection,
    *,
    since: float | None = None,
    config: VerticalKeywordsFile | None = None,
) -> list[VerticalHitSummary]:
    params: tuple = ()
    where = ""
    if since is not None:
        where = "WHERE kh.hit_ts >= ?"
        params = (since,)
    rows = conn.execute(
        f"""
        SELECT kh.keyword,
               kh.station_id,
               MAX(kh.hit_ts) AS hit_ts,
               COUNT(*) AS hits
        FROM keyword_hits kh
        {where}
        GROUP BY kh.keyword, kh.station_id
        """,
        params,
    ).fetchall()
    return classify_vertical_hits(rows, config=config)


def vertical_slug(vertical_id: str) -> str:
    return vertical_id.replace("_", "-")


def vertical_id_from_slug(slug: str) -> str:
    return slug.replace("-", "_")


def source_keywords_json(keywords: tuple[str, ...] | list[str]) -> str:
    return json.dumps(list(keywords))

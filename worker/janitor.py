"""Chunk WAV retention cleanup for transient storage (disk or tmpfs)."""

from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from shared.db import checkpoint_wal, get_connection, retry_on_busy, transaction
from shared.metrics import increment_chunk_files_deleted, set_wal_checkpoint_metrics
from shared.models import ChunkStatus, PipelineSettings

logger = logging.getLogger("worker.janitor")

STATUS_KEY_STATION_DAILY_LAST = "janitor:station_daily:last_date"


def delete_chunk_file(path: str | Path) -> bool:
    """Delete a chunk WAV when present. Returns True if a file was removed."""
    file_path = Path(path)
    if not file_path.is_file():
        return False
    file_path.unlink(missing_ok=True)
    increment_chunk_files_deleted()
    return True


class ChunkJanitor:
    """Delete transient chunk audio while keeping SQLite metadata and ad archives."""

    def __init__(
        self,
        db_path: str | Path,
        settings: PipelineSettings,
        *,
        chunks_dir: str | Path | None = None,
        archive_dir: str | Path = "data/ad_archive",
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.settings = settings
        self.chunks_dir = Path(chunks_dir or settings.chunks_dir)
        self.archive_dir = Path(archive_dir).resolve()
        self._now = now_fn or time.time

    def delete_after_processing(self, path: str | Path) -> bool:
        """Remove a chunk WAV after worker processing completes."""
        file_path = Path(path).resolve()
        if self._is_protected_path(file_path):
            return False
        return delete_chunk_file(file_path)

    @retry_on_busy()
    def expire_stale_pending(self) -> int:
        """Drop pending chunks older than retention_hours and delete their files."""
        cutoff = self._now() - (self.settings.retention_hours * 3600)
        conn = get_connection(self.db_path)
        removed = 0
        try:
            rows = conn.execute(
                """
                SELECT id, station_id, path, start_ts, end_ts
                FROM chunks
                WHERE status = ?
                  AND start_ts < ?
                """,
                (ChunkStatus.PENDING.value, cutoff),
            ).fetchall()
            if not rows:
                return 0

            with transaction(conn):
                for row in rows:
                    conn.execute(
                        """
                        UPDATE chunks
                        SET status = ?, error = ?
                        WHERE id = ?
                        """,
                        (ChunkStatus.DROPPED.value, "retention_expired", row["id"]),
                    )
                    conn.execute(
                        """
                        INSERT INTO gaps (station_id, start_ts, end_ts, reason)
                        VALUES (?, ?, ?, 'retention_expired')
                        """,
                        (row["station_id"], row["start_ts"], row["end_ts"]),
                    )
                    if delete_chunk_file(row["path"]):
                        removed += 1
        finally:
            conn.close()

        if removed:
            logger.info(
                "expired stale pending chunks",
                extra={"count": len(rows), "files_deleted": removed},
            )
        return len(rows)

    @retry_on_busy()
    def cleanup_dropped_files(self) -> int:
        """Delete WAV files for chunks already marked dropped."""
        conn = get_connection(self.db_path)
        removed = 0
        try:
            rows = conn.execute(
                """
                SELECT path
                FROM chunks
                WHERE status = ?
                """,
                (ChunkStatus.DROPPED.value,),
            ).fetchall()
            for row in rows:
                if delete_chunk_file(row["path"]):
                    removed += 1
        finally:
            conn.close()
        return removed

    def sweep_orphans(self) -> int:
        """Delete chunk files under chunks_dir with no matching DB row."""
        if not self.chunks_dir.is_dir():
            return 0

        known_paths = self._known_chunk_paths()
        removed = 0
        for file_path in self.chunks_dir.rglob("*.wav"):
            resolved = file_path.resolve()
            if self._is_protected_path(resolved):
                continue
            if str(resolved) not in known_paths and delete_chunk_file(resolved):
                removed += 1
        return removed

    def passive_wal_checkpoint(self) -> int:
        """Fold WAL pages when idle; log and continue on busy or failure."""
        try:
            result = checkpoint_wal(self.db_path, mode="PASSIVE")
            set_wal_checkpoint_metrics(result)
            if result.busy:
                logger.debug(
                    "wal checkpoint passive busy",
                    extra={
                        "log_frames": result.log_frames,
                        "checkpointed_frames": result.checkpointed_frames,
                    },
                )
            return result.checkpointed_frames
        except Exception:
            logger.warning("wal checkpoint failed", exc_info=True)
            return 0

    def run_sweep(self) -> dict[str, int]:
        """Run periodic janitor tasks."""
        return {
            "wal_checkpointed_frames": self.passive_wal_checkpoint(),
            "expired_pending": self.expire_stale_pending(),
            "dropped_files_removed": self.cleanup_dropped_files(),
            "orphans_removed": self.sweep_orphans(),
            "station_daily_rows": self.rollup_station_daily(),
        }

    @retry_on_busy()
    def rollup_station_daily(self, *, target_date: str | None = None) -> int:
        """Aggregate yesterday (UTC) into station_daily once per calendar day."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        conn = get_connection(self.db_path)
        try:
            last_row = conn.execute(
                "SELECT value FROM status WHERE key = ?",
                (STATUS_KEY_STATION_DAILY_LAST,),
            ).fetchone()
            if last_row and last_row["value"] == today and target_date is None:
                return 0

            if target_date is None:
                target_date = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()

            start_ts = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp()
            end_ts = start_ts + 24 * 3600
            stations = conn.execute("SELECT id FROM stations").fetchall()
            upserted = 0
            with transaction(conn):
                for station_row in stations:
                    station_id = int(station_row["id"])
                    chunks_count = conn.execute(
                        """
                        SELECT COUNT(*) FROM chunks
                        WHERE station_id = ? AND start_ts >= ? AND start_ts < ?
                        """,
                        (station_id, start_ts, end_ts),
                    ).fetchone()[0]
                    gap_count = conn.execute(
                        """
                        SELECT COUNT(*) FROM gaps
                        WHERE station_id = ? AND start_ts >= ? AND start_ts < ?
                        """,
                        (station_id, start_ts, end_ts),
                    ).fetchone()[0]
                    keyword_hits = conn.execute(
                        """
                        SELECT COUNT(*) FROM keyword_hits
                        WHERE station_id = ? AND hit_ts >= ? AND hit_ts < ?
                        """,
                        (station_id, start_ts, end_ts),
                    ).fetchone()[0]
                    unique_keywords = conn.execute(
                        """
                        SELECT COUNT(DISTINCT keyword) FROM keyword_hits
                        WHERE station_id = ? AND hit_ts >= ? AND hit_ts < ?
                        """,
                        (station_id, start_ts, end_ts),
                    ).fetchone()[0]
                    loan_detections = conn.execute(
                        """
                        SELECT COUNT(*) FROM detections d
                        JOIN chunks c ON c.id = d.chunk_id
                        WHERE c.station_id = ?
                          AND c.start_ts >= ? AND c.start_ts < ?
                          AND d.is_ad = 1
                        """,
                        (station_id, start_ts, end_ts),
                    ).fetchone()[0]
                    conn.execute(
                        """
                        INSERT INTO station_daily (
                            station_id, date, chunks_count, gap_count,
                            keyword_hits, unique_keywords, loan_detections
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(station_id, date) DO UPDATE SET
                            chunks_count = excluded.chunks_count,
                            gap_count = excluded.gap_count,
                            keyword_hits = excluded.keyword_hits,
                            unique_keywords = excluded.unique_keywords,
                            loan_detections = excluded.loan_detections
                        """,
                        (
                            station_id,
                            target_date,
                            int(chunks_count),
                            int(gap_count),
                            int(keyword_hits),
                            int(unique_keywords),
                            int(loan_detections),
                        ),
                    )
                    upserted += 1

                conn.execute(
                    """
                    INSERT INTO status (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (STATUS_KEY_STATION_DAILY_LAST, today, self._now()),
                )
            return upserted
        finally:
            conn.close()

    def _known_chunk_paths(self) -> set[str]:
        conn = get_connection(self.db_path, read_only=True)
        try:
            rows = conn.execute("SELECT path FROM chunks").fetchall()
        finally:
            conn.close()
        return {str(Path(row["path"]).resolve()) for row in rows}

    def _is_protected_path(self, path: Path) -> bool:
        try:
            path.relative_to(self.archive_dir)
        except ValueError:
            return False
        return True

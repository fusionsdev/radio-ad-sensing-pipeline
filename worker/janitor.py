"""Chunk WAV retention cleanup for transient storage (disk or tmpfs)."""

from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

from shared.db import checkpoint_wal, get_connection, retry_on_busy, transaction
from shared.metrics import increment_chunk_files_deleted, set_wal_checkpoint_metrics
from shared.models import ChunkStatus, PipelineSettings

logger = logging.getLogger("worker.janitor")


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
        }

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

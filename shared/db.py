"""SQLite connection factory, migrations, and SQLITE_BUSY retry wrapper."""

from __future__ import annotations

import functools
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, ParamSpec, TypeVar

WalCheckpointMode = Literal["PASSIVE", "FULL", "RESTART", "TRUNCATE"]

P = ParamSpec("P")
R = TypeVar("R")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

EXPECTED_TABLES = (
    "stations",
    "chunks",
    "transcripts",
    "canonical_ads",
    "detections",
    "gaps",
    "fingerprints",
    "keyword_hits",
    "station_daily",
    "status",
    "schema_migrations",
)


def _is_busy_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return "locked" in message or "busy" in message


def retry_on_busy(
    *,
    max_retries: int = 5,
    base_delay: float = 0.01,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Retry a callable when SQLite reports database is locked or busy."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exc: sqlite3.OperationalError | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as exc:
                    if not _is_busy_error(exc):
                        raise
                    last_exc = exc
                    if attempt == max_retries:
                        raise
                    time.sleep(base_delay * (2**attempt))
            raise last_exc  # pragma: no cover

        return wrapper

    return decorator


@dataclass(frozen=True)
class WalCheckpointResult:
    """Result of PRAGMA wal_checkpoint(mode)."""

    busy: bool
    log_frames: int
    checkpointed_frames: int


def get_connection(
    db_path: str | Path,
    *,
    read_only: bool = False,
) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and busy_timeout=5000."""
    path = Path(db_path)

    if read_only:
        uri = f"file:{path.resolve()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)

    conn.row_factory = sqlite3.Row
    if not read_only:
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def checkpoint_wal(
    db_path: str | Path,
    *,
    mode: WalCheckpointMode = "PASSIVE",
) -> WalCheckpointResult:
    """Run PRAGMA wal_checkpoint; passive mode never blocks writers."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(f"PRAGMA wal_checkpoint({mode})").fetchone()
        if row is None:
            raise RuntimeError("wal_checkpoint returned no row")
        return WalCheckpointResult(
            busy=bool(row[0]),
            log_frames=int(row[1]),
            checkpointed_frames=int(row[2]),
        )
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Short transaction context manager with automatic commit/rollback."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at REAL NOT NULL
        )
        """
    )
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row[0] for row in rows}


@retry_on_busy()
def migrate(db_path: str | Path) -> list[int]:
    """Apply pending numbered SQL migrations. Returns applied version numbers."""
    applied: list[int] = []
    conn = get_connection(db_path)
    try:
        already = _applied_versions(conn)
        for migration_file in _migration_files():
            version = int(migration_file.stem.split("_", 1)[0])
            if version in already:
                continue
            sql = migration_file.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, time.time()),
            )
            conn.commit()
            applied.append(version)
    finally:
        conn.close()
    return applied


def list_tables(db_path: str | Path) -> list[str]:
    """Return user table names in the database."""
    conn = get_connection(db_path, read_only=True)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return sorted(row[0] for row in rows)
    finally:
        conn.close()

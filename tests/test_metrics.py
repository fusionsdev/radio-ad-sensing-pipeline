"""Tests for Prometheus metric helpers."""

from __future__ import annotations

from shared.db import WalCheckpointResult
from shared.metrics import (
    SQLITE_WAL_BUSY,
    SQLITE_WAL_CHECKPOINTED_FRAMES,
    SQLITE_WAL_LOG_FRAMES,
    set_wal_checkpoint_metrics,
)


def test_set_wal_checkpoint_metrics_updates_gauges() -> None:
    set_wal_checkpoint_metrics(
        WalCheckpointResult(busy=True, log_frames=12, checkpointed_frames=7)
    )
    assert SQLITE_WAL_LOG_FRAMES._value.get() == 12.0  # noqa: SLF001
    assert SQLITE_WAL_CHECKPOINTED_FRAMES._value.get() == 7.0  # noqa: SLF001
    assert SQLITE_WAL_BUSY._value.get() == 1.0  # noqa: SLF001

    set_wal_checkpoint_metrics(
        WalCheckpointResult(busy=False, log_frames=0, checkpointed_frames=0)
    )
    assert SQLITE_WAL_BUSY._value.get() == 0.0  # noqa: SLF001

"""Queue health helpers shared across dashboard and watchdog."""

from __future__ import annotations


def compute_queue_drop_ratio(*, dropped: int, done: int) -> float:
    """Dropped-to-done ratio for queue health monitoring."""
    if done <= 0:
        return float(dropped) if dropped > 0 else 0.0
    return round(dropped / done, 2)


def queue_drop_warning(*, dropped: int, done: int, threshold: float) -> bool:
    return compute_queue_drop_ratio(dropped=dropped, done=done) >= threshold

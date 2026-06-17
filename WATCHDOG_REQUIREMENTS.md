# Station Watchdog + Auto-Recovery + Replacement Pool Requirements

## 1. Overview and Problem Statement

The core problem is system instability leading to unexpected halts in the autonomous radio ad-sensing pipeline. The primary goal is to implement a robust self-healing mechanism to ensure continuous operation of up to 10 active stations concurrently. This system will detect station failures (stalling, dying, not producing chunks), attempt recovery, and if unsuccessful, temporarily disable the unhealthy station and promote a backup from a replacement pool to maintain the target active station count.

**Advantages of this approach:**
- Increased system resilience and uptime, minimizing data loss and missed detections.
- Automated recovery reduces manual intervention and operational overhead.
- Maintains a consistent throughput by ensuring a target number of stations are always active.

**Disadvantages/Tradeoffs:**
- Adds complexity to the system architecture, requiring careful design and testing.
- Potential for "flapping" if recovery mechanisms are too aggressive or misconfigured.
- Resource contention if too many recovery attempts are made simultaneously.

## 2. Core Definitions

-   **Active:** `enabled=true` AND `health_state` in `active/running/recovering`
-   **Healthy:** Recent chunks, no repeated `ffmpeg` failures
-   **Stalled:** `enabled` but no chunk within `station_stale_after_minutes` (default 6)
-   **Failed:** Consecutive failures >= `restart_attempts_before_disable` OR daily max failures OR repeated `ffmpeg`/stream validation failures
-   **Backup:** `enabled=false`, available for promotion
-   **Replacement pool:** `replacement_eligible=true`, `health_state` not `banned`/`permanently_failed`

## 3. Architectural Constraints

-   Python 3.11+
-   Docker Compose
-   SQLite WAL
-   No Redis/Celery/PostgreSQL
-   Services: `ingestor` (ffmpeg per-station threads), `worker` (faster-whisper/Ollama/rapidfuzz), `alerter` (Telegram), `dashboard` (FastAPI/HTMX), Prometheus/Grafana
-   Existing tables: `stations`, `chunks`, `gaps`, `status`, `station_daily`, `detections`, `transcripts`
-   `Ingestor` uses `StationIngestor` per enabled station in threads (`ingestor/supervisor.py`)
-   Local-first single-box architecture

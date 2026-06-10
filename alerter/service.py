"""Telegram outbound alerter service for first-seen, ops, and digest alerts."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from shared.config import TelegramSettings, load_settings, load_telegram_settings
from shared.db import get_connection, transaction
from shared.logging import setup_logging
from shared.metrics import increment_alerts_sent, increment_chunks_processed, set_queue_pending_hours
from shared.models import PipelineSettings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLL_INTERVAL_SECONDS = 30
TELEGRAM_MESSAGE_LIMIT = 4096
TRANSCRIPT_EXCERPT_LIMIT = 2800

STATUS_KEY_QUEUE_DROPS_LAST_ID = "alerter:queue_drops:last_id"
STATUS_KEY_DIGEST_DATE = "alerter:digest:date"
STATUS_KEY_STATION_DOWN_PREFIX = "alerter:station_down:"


@dataclass(frozen=True)
class FirstSeenAlert:
    """A detection row that has not been alerted yet."""

    detection_id: int
    chunk_id: int
    station_name: str
    station_id: int
    start_ts: float
    end_ts: float
    company_name: str | None
    ad_category: str | None
    phone_number: str | None
    website: str | None
    offer_summary: str | None
    confidence: float | None
    archived_audio_path: str | None
    transcript_text: str | None


@dataclass(frozen=True)
class StationDownAlert:
    station_id: int
    station_name: str
    outage_start_ts: float
    last_chunk_ts: float | None
    latest_gap_ts: float | None


class TelegramBotApi:
    """Tiny HTTP wrapper around the Telegram Bot API."""

    def __init__(
        self,
        token: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=f"https://api.telegram.org/bot{token}",
            transport=transport,
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def send_message(self, chat_id: str, text: str) -> None:
        response = self._client.post(
            "sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok", False):
            raise RuntimeError(f"Telegram sendMessage failed: {payload!r}")

    def send_audio(self, chat_id: str, audio_path: Path, *, caption: str | None = None) -> None:
        with audio_path.open("rb") as handle:
            files = {
                "audio": (audio_path.name, handle, "audio/wav"),
            }
            data: dict[str, str] = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
            response = self._client.post("sendAudio", data=data, files=files)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok", False):
            raise RuntimeError(f"Telegram sendAudio failed: {payload!r}")


class AlerterService:
    """Poll the database and emit Telegram alerts."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        settings: PipelineSettings | None = None,
        telegram_settings: TelegramSettings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        client: TelegramBotApi | None = None,
        clock: Callable[[], float] = time.time,
        logger: Any | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.db_path = Path(db_path or self.settings.db_path)
        self.telegram_settings = telegram_settings or load_telegram_settings()
        self.clock = clock
        self.log = logger or setup_logging("alerter")
        self._dry_run = not (
            self.telegram_settings.telegram_bot_token and self.telegram_settings.telegram_chat_id
        )
        self._client = client
        if self._client is None and not self._dry_run:
            self._client = TelegramBotApi(
                self.telegram_settings.telegram_bot_token or "",
                transport=transport,
            )

        if self._dry_run:
            self.log.info("alerter running in dry-run mode because TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is unset")

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def run(self, stop_event: threading.Event | None = None, *, poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS) -> None:
        """Run the poll loop until stopped."""
        try:
            while True:
                self.poll_once()
                if stop_event is None:
                    time.sleep(poll_interval_seconds)
                    continue
                if stop_event.wait(poll_interval_seconds):
                    break
        finally:
            self.close()

    def poll_once(self) -> dict[str, int]:
        """Process any pending alerts once and return a small activity summary."""
        now_ts = self.clock()
        summary = {"first_seen": 0, "ops": 0, "digest": 0}
        conn = get_connection(self.db_path)
        try:
            first_seen = self._load_first_seen_alerts(conn)
            for alert in first_seen:
                if self._send_first_seen_alert(alert):
                    self._mark_detection_alerted(conn, alert.detection_id)
                    summary["first_seen"] += 1

            ops_alerts = self._load_station_down_alerts(conn, now_ts)
            for alert in ops_alerts:
                if self._send_station_down_alert(alert, now_ts):
                    self._mark_station_down_alerted(conn, alert.station_id, alert.outage_start_ts, now_ts)
                    summary["ops"] += 1

            queue_drop_alert = self._load_queue_drop_alert(conn)
            if queue_drop_alert and self._send_queue_drop_alert(queue_drop_alert, now_ts):
                with transaction(conn):
                    self._mark_status(
                        conn,
                        STATUS_KEY_QUEUE_DROPS_LAST_ID,
                        str(queue_drop_alert["last_id"]),
                        now_ts,
                    )
                summary["ops"] += 1

            digest = self._load_daily_digest(conn, now_ts)
            if digest and self._send_daily_digest(digest, now_ts):
                with transaction(conn):
                    self._mark_status(conn, STATUS_KEY_DIGEST_DATE, digest["digest_date"], now_ts)
                summary["digest"] += 1
        finally:
            conn.close()
            set_queue_pending_hours(self.db_path)
        processed_total = sum(summary.values())
        if processed_total:
            increment_chunks_processed("alerter", amount=processed_total)
        return summary

    def _load_first_seen_alerts(self, conn) -> list[FirstSeenAlert]:
        rows = conn.execute(
            """
            SELECT d.id AS detection_id,
                   d.chunk_id,
                   d.company_name,
                   d.ad_category,
                   d.phone_number,
                   d.website,
                   d.offer_summary,
                   d.confidence,
                   c.id AS chunk_row_id,
                   c.station_id,
                   c.start_ts,
                   c.end_ts,
                   s.name AS station_name,
                   ca.archived_audio_path,
                   t.text AS transcript_text
            FROM detections d
            JOIN chunks c ON c.id = d.chunk_id
            JOIN stations s ON s.id = c.station_id
            LEFT JOIN canonical_ads ca ON ca.id = d.canonical_ad_id
            LEFT JOIN transcripts t ON t.chunk_id = d.chunk_id
            WHERE d.alerted = 0 AND d.is_ad = 1
            ORDER BY d.id
            """
        ).fetchall()
        return [
            FirstSeenAlert(
                detection_id=int(row["detection_id"]),
                chunk_id=int(row["chunk_id"]),
                station_name=row["station_name"],
                station_id=int(row["station_id"]),
                start_ts=float(row["start_ts"]),
                end_ts=float(row["end_ts"]),
                company_name=row["company_name"],
                ad_category=row["ad_category"],
                phone_number=row["phone_number"],
                website=row["website"],
                offer_summary=row["offer_summary"],
                confidence=float(row["confidence"]) if row["confidence"] is not None else None,
                archived_audio_path=row["archived_audio_path"],
                transcript_text=row["transcript_text"],
            )
            for row in rows
        ]

    def _load_station_down_alerts(self, conn, now_ts: float) -> list[StationDownAlert]:
        threshold_seconds = self.settings.station_down_alert_minutes * 60
        rows = conn.execute(
            """
            SELECT s.id AS station_id,
                   s.name AS station_name,
                   MAX(c.end_ts) AS last_chunk_ts
            FROM stations s
            LEFT JOIN chunks c ON c.station_id = s.id
            WHERE s.enabled = 1
            GROUP BY s.id
            ORDER BY s.name
            """
        ).fetchall()
        alerts: list[StationDownAlert] = []
        for row in rows:
            station_id = int(row["station_id"])
            last_chunk_ts = float(row["last_chunk_ts"]) if row["last_chunk_ts"] is not None else None
            outage_start_ts = self._outage_start_ts(conn, station_id, last_chunk_ts)
            if outage_start_ts is None:
                continue
            if now_ts - outage_start_ts < threshold_seconds:
                continue
            marker = f"{outage_start_ts:.3f}"
            if self._status_value(conn, f"{STATUS_KEY_STATION_DOWN_PREFIX}{station_id}") == marker:
                continue
            latest_gap = conn.execute(
                """
                SELECT MAX(start_ts) AS latest_gap_ts
                FROM gaps
                WHERE station_id = ? AND reason = 'stream_down'
                """,
                (station_id,),
            ).fetchone()["latest_gap_ts"]
            alerts.append(
                StationDownAlert(
                    station_id=station_id,
                    station_name=row["station_name"],
                    outage_start_ts=outage_start_ts,
                    last_chunk_ts=last_chunk_ts,
                    latest_gap_ts=float(latest_gap) if latest_gap is not None else None,
                )
            )
        return alerts

    def _outage_start_ts(self, conn, station_id: int, last_chunk_ts: float | None) -> float | None:
        cutoff = last_chunk_ts if last_chunk_ts is not None else 0.0
        row = conn.execute(
            """
            SELECT MIN(start_ts) AS outage_start_ts
            FROM gaps
            WHERE station_id = ?
              AND reason = 'stream_down'
              AND start_ts >= ?
            """,
            (station_id, cutoff),
        ).fetchone()
        outage_start_ts = row["outage_start_ts"]
        if outage_start_ts is not None:
            return float(outage_start_ts)
        if last_chunk_ts is not None:
            return float(last_chunk_ts)
        return None

    def _load_queue_drop_alert(self, conn) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT MAX(id) AS last_id FROM chunks WHERE status = 'dropped'"
        ).fetchone()
        last_id = row["last_id"]
        if last_id is None:
            return None
        last_id_int = int(last_id)
        marker = self._status_value(conn, STATUS_KEY_QUEUE_DROPS_LAST_ID)
        if marker is not None and marker == str(last_id_int):
            return None
        new_rows = conn.execute(
            """
            SELECT id, path, error
            FROM chunks
            WHERE status = 'dropped' AND id > ?
            ORDER BY id
            """,
            (int(marker) if marker and marker.isdigit() else 0,),
        ).fetchall()
        reasons = [row["error"] or "unknown" for row in new_rows]
        return {
            "last_id": last_id_int,
            "count": len(new_rows),
            "reasons": reasons,
        }

    def _load_daily_digest(self, conn, now_ts: float) -> dict[str, Any] | None:
        digest_date = datetime.fromtimestamp(now_ts, tz=UTC).date().isoformat()
        if self._status_value(conn, STATUS_KEY_DIGEST_DATE) == digest_date:
            return None
        since = datetime.fromtimestamp(now_ts, tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        alerted_today = conn.execute(
            """
            SELECT COUNT(*)
            FROM detections d
            JOIN chunks c ON c.id = d.chunk_id
            WHERE d.alerted = 1 AND c.start_ts >= ?
            """,
            (since,),
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE status = 'pending'"
        ).fetchone()[0]
        dropped_today = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE status = 'dropped' AND start_ts >= ?",
            (since,),
        ).fetchone()[0]
        down_now = self._load_station_down_alerts(conn, now_ts)
        return {
            "digest_date": digest_date,
            "alerted_today": int(alerted_today),
            "pending": int(pending),
            "dropped_today": int(dropped_today),
            "down_stations": down_now,
        }

    def _send_first_seen_alert(self, alert: FirstSeenAlert) -> bool:
        message = self._format_first_seen_message(alert)
        if self._dry_run:
            self.log.info(message)
            if alert.archived_audio_path:
                audio_path = self._resolve_audio_path(alert.archived_audio_path)
                if audio_path is not None:
                    self.log.info("dry-run audio: %s", audio_path)
            self._record_alert_sent("first_seen", success=True)
            return True
        assert self._client is not None
        try:
            self._client.send_message(self.telegram_settings.telegram_chat_id or "", message)
            if alert.archived_audio_path:
                audio_path = self._resolve_audio_path(alert.archived_audio_path)
                if audio_path is not None:
                    self._client.send_audio(self.telegram_settings.telegram_chat_id or "", audio_path, caption=alert.company_name or "ad archive")
            self._record_alert_sent("first_seen", success=True)
            return True
        except Exception:
            self.log.exception("failed to send first-seen alert", extra={"detection_id": alert.detection_id})
            self._record_alert_sent("first_seen", success=False)
            return False

    def _send_station_down_alert(self, alert: StationDownAlert, now_ts: float) -> bool:
        duration_minutes = int((now_ts - alert.outage_start_ts) // 60)
        message = (
            f"Ops alert: station down > {self.settings.station_down_alert_minutes} min\n"
            f"Station: {alert.station_name}\n"
            f"Down since: {self._format_ts(alert.outage_start_ts)}\n"
            f"Current outage: {duration_minutes} min\n"
            f"Last chunk: {self._format_ts(alert.last_chunk_ts) if alert.last_chunk_ts is not None else 'none'}"
        )
        if self._dry_run:
            self.log.info(message)
            self._record_alert_sent("station_down", success=True)
            return True
        assert self._client is not None
        try:
            self._client.send_message(self.telegram_settings.telegram_chat_id or "", message)
            self._record_alert_sent("station_down", success=True)
            return True
        except Exception:
            self.log.exception("failed to send station down alert", extra={"station_id": alert.station_id})
            self._record_alert_sent("station_down", success=False)
            return False

    def _send_queue_drop_alert(self, alert: dict[str, Any], now_ts: float) -> bool:
        message = (
            "Ops alert: queue drops\n"
            f"New dropped chunks: {alert['count']}\n"
            f"Latest chunk id: {alert['last_id']}\n"
            f"Generated at: {self._format_ts(now_ts)}"
        )
        if alert["reasons"]:
            unique_reasons = ", ".join(sorted(set(alert["reasons"])))
            message += f"\nReasons: {unique_reasons}"
        if self._dry_run:
            self.log.info(message)
            self._record_alert_sent("queue_drop", success=True)
            return True
        assert self._client is not None
        try:
            self._client.send_message(self.telegram_settings.telegram_chat_id or "", message)
            self._record_alert_sent("queue_drop", success=True)
            return True
        except Exception:
            self.log.exception("failed to send queue drop alert")
            self._record_alert_sent("queue_drop", success=False)
            return False

    def _send_daily_digest(self, digest: dict[str, Any], now_ts: float) -> bool:
        message = (
            f"Daily digest {digest['digest_date']}\n"
            f"First-seen alerts sent: {digest['alerted_today']}\n"
            f"Pending queue: {digest['pending']}\n"
            f"Dropped chunks today: {digest['dropped_today']}\n"
            f"Stations currently down: {len(digest['down_stations'])}"
        )
        if digest["down_stations"]:
            names = ", ".join(alert.station_name for alert in digest["down_stations"])
            message += f"\nDown stations: {names}"
        if self._dry_run:
            self.log.info(message)
            self._record_alert_sent("digest", success=True)
            return True
        assert self._client is not None
        try:
            self._client.send_message(self.telegram_settings.telegram_chat_id or "", message)
            self._record_alert_sent("digest", success=True)
            return True
        except Exception:
            self.log.exception("failed to send daily digest")
            self._record_alert_sent("digest", success=False)
            return False

    def _record_alert_sent(self, alert_type: str, *, success: bool) -> None:
        if self._dry_run:
            outcome = "dry_run"
        else:
            outcome = "success" if success else "fail"
        increment_alerts_sent(alert_type, outcome)

    def _format_first_seen_message(self, alert: FirstSeenAlert) -> str:
        lines = [
            "First-seen ad alert",
            f"Station: {alert.station_name}",
            f"Company: {alert.company_name or 'unknown'}",
            f"Category: {alert.ad_category or 'unknown'}",
            f"Phone: {alert.phone_number or 'unknown'}",
            f"Website: {alert.website or 'unknown'}",
            f"Confidence: {self._format_confidence(alert.confidence)}",
            f"Chunk: {self._format_ts(alert.start_ts)}",
        ]
        if alert.offer_summary:
            lines.append(f"Summary: {alert.offer_summary}")
        if alert.transcript_text:
            lines.append(f"Transcript: {self._truncate_transcript(alert.transcript_text)}")
        message = "\n".join(lines)
        if len(message) > TELEGRAM_MESSAGE_LIMIT:
            return message[: TELEGRAM_MESSAGE_LIMIT - 3].rstrip() + "..."
        return message

    def _truncate_transcript(self, text: str) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= TRANSCRIPT_EXCERPT_LIMIT:
            return normalized
        return normalized[: TRANSCRIPT_EXCERPT_LIMIT - 3].rstrip() + "..."

    def _resolve_audio_path(self, stored_path: str | None) -> Path | None:
        if not stored_path:
            return None
        path = Path(stored_path)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        else:
            path = path.resolve()
        if path.is_file():
            return path
        return None

    def _format_confidence(self, confidence: float | None) -> str:
        if confidence is None:
            return "unknown"
        return f"{confidence * 100:.0f}%"

    def _format_ts(self, timestamp: float | None) -> str:
        if timestamp is None:
            return "unknown"
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()

    def _status_value(self, conn, key: str) -> str | None:
        row = conn.execute("SELECT value FROM status WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return row["value"]

    def _mark_detection_alerted(self, conn, detection_id: int) -> None:
        with transaction(conn):
            conn.execute(
                "UPDATE detections SET alerted = 1 WHERE id = ?",
                (detection_id,),
            )

    def _mark_station_down_alerted(self, conn, station_id: int, outage_start_ts: float, now_ts: float) -> None:
        with transaction(conn):
            self._mark_status(
                conn,
                f"{STATUS_KEY_STATION_DOWN_PREFIX}{station_id}",
                f"{outage_start_ts:.3f}",
                now_ts,
            )

    def _mark_status(self, conn, key: str, value: str, now_ts: float) -> None:
        conn.execute(
            """
            INSERT INTO status (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, now_ts),
        )

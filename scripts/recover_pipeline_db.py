"""One-off: recover corrupted pipeline.db via backup or VACUUM INTO."""
from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SRC = DATA / "pipeline.db"
DST = DATA / "pipeline_vacuum.db"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")

    bak = DATA / "pipeline.db.bak2"
    if not bak.exists():
        shutil.copy2(SRC, bak)
        print(f"backup -> {bak}")

    if DST.exists():
        DST.unlink()

    src_conn = sqlite3.connect(SRC)
    try:
        src_conn.execute(f"VACUUM INTO '{DST.as_posix()}'")
        src_conn.commit()
        print("VACUUM INTO ok")
    except sqlite3.Error as exc:
        print(f"VACUUM INTO failed: {exc}; trying backup API")
        dst_conn = sqlite3.connect(DST)
        pages = src_conn.backup(dst_conn)
        dst_conn.close()
        print(f"backup API pages={pages}")
    finally:
        src_conn.close()

    dst_conn = sqlite3.connect(DST)
    try:
        integrity = dst_conn.execute("PRAGMA integrity_check").fetchone()[0]
        print("integrity:", integrity[:200] if len(integrity) > 200 else integrity)
        for table in ("chunks", "cfpb_complaints_raw", "cfpb_brand_candidates", "cfpb_collection_runs"):
            try:
                n = dst_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"{table}: {n}")
            except sqlite3.Error as err:
                print(f"{table}: ERROR {err}")
    finally:
        dst_conn.close()


if __name__ == "__main__":
    main()

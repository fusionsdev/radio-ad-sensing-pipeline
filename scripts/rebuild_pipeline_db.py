"""Rebuild pipeline.db by row-copying all tables except known-corrupt ones."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SRC = DATA / "pipeline.db"
DST = DATA / "pipeline_rebuilt.db"
SKIP_TABLES = {"cfpb_brand_candidates", "sqlite_sequence"}


def main() -> None:
    if DST.exists():
        DST.unlink()

    src = sqlite3.connect(SRC)
    dst = sqlite3.connect(DST)
    src.row_factory = sqlite3.Row

    try:
        tables = [
            r[0]
            for r in src.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        print("tables:", len(tables))

        for name in tables:
            if name in SKIP_TABLES:
                print(f"skip {name}")
                continue
            ddl = src.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()[0]
            dst.execute(ddl)
            rows = src.execute(f"SELECT * FROM {name}").fetchall()
            if not rows:
                print(f"{name}: 0")
                continue
            cols = rows[0].keys()
            placeholders = ",".join("?" * len(cols))
            col_list = ",".join(cols)
            dst.executemany(
                f"INSERT INTO {name} ({col_list}) VALUES ({placeholders})",
                [tuple(r[c] for c in cols) for r in rows],
            )
            print(f"{name}: {len(rows)}")

        # Recreate dropped/skipped CFPB tables from DDL in source schema
        for name in SKIP_TABLES:
            if name == "sqlite_sequence":
                continue
            row = src.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            if row and row[0]:
                dst.execute(row[0])
                print(f"recreated empty {name}")

        dst.commit()
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
        print("integrity:", integrity)
        for t in ("chunks", "cfpb_complaints_raw", "cfpb_brand_candidates", "cfpb_company_entities"):
            n = dst.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"{t}: {n}")
    finally:
        src.close()
        dst.close()

    backup = DATA / "pipeline.db.corrupt"
    if not backup.exists():
        SRC.rename(backup)
    else:
        SRC.unlink()
    DST.rename(SRC)
    print(f"replaced pipeline.db (old -> {backup.name})")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

MIGRATIONS: list[dict] = [
    {
        "version": 1,
        "description": "Initial schema — jobs and job_events tables",
        "sql": """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT,
                error TEXT,
                files TEXT DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL REFERENCES jobs(id),
                event TEXT NOT NULL,
                data TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON job_events(job_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        """,
    },
]


def get_db_path() -> str:
    return os.environ.get("VIDEO_REV_DB_PATH", ".cache/videoreverse.db")


def get_current_version(db_path: str) -> int:
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute("PRAGMA user_version").fetchone()
        conn.close()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def migrate(db_path: str, target_version: int | None = None) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    current = get_current_version(db_path)
    target = target_version or len(MIGRATIONS)
    pending = [m for m in MIGRATIONS if m["version"] > current and m["version"] <= target]

    if not pending:
        print(f"DB is at version {current}/{len(MIGRATIONS)} — nothing to do.")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        for migration in pending:
            print(f"Applying migration v{migration['version']}: {migration['description']}")
            conn.executescript(migration["sql"])
            conn.execute(f"PRAGMA user_version = {migration['version']}")
            conn.commit()
            print("  → Done")
        print(f"Migrated from v{current} to v{target}")
    except sqlite3.Error as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def list_migrations() -> None:
    for m in MIGRATIONS:
        print(f"  v{m['version']}: {m['description']}")


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_migrations()
        sys.exit(0)

    db_path = get_db_path()
    target = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--target" and i < len(sys.argv):
            target = int(sys.argv[i + 1])
            break
        if arg == "--db":
            db_path = sys.argv[i + 1] if i < len(sys.argv) else db_path
            break

    migrate(db_path, target)

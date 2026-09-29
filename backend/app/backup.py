"""Database backups (Blueprint section K "Backups", launch gate O "backup restored once").

    python -m app.backup              make a backup, then verify it restores
    python -m app.backup --list       show backups
    python -m app.backup --verify F   check an existing backup restores
    python -m app.backup --restore F --yes
                                      put a backup back (SQLite only); the
                                      current database is backed up first

Backups go to BACKUP_DIR (default: backend/backups). Nothing is ever deleted
unless you pass --keep N, which keeps only the newest N backups. Copy the
folder to an external drive or cloud storage regularly.

SQLite uses the built-in online backup API (safe while the shop is running).
PostgreSQL uses pg_dump / pg_restore, which must be on PATH.
"""

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

from .config import settings

KEY_TABLES = ("products", "orders", "order_items", "admin_audit")
BACKEND_DIR = Path(__file__).resolve().parent.parent


class BackupError(Exception):
    pass


def backup_dir() -> Path:
    d = Path(os.environ.get("BACKUP_DIR") or BACKEND_DIR / "backups")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sqlite_path(url: str) -> Path:
    db = make_url(url).database
    if not db or db == ":memory:":
        raise BackupError("In-memory SQLite databases cannot be backed up")
    p = Path(db)
    return p if p.is_absolute() else Path.cwd() / p


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _new_path(dest_dir: Path, suffix: str) -> Path:
    """A fresh file name; an existing backup is never overwritten."""
    base = f"novahaus-{_stamp()}"
    path = dest_dir / f"{base}{suffix}"
    n = 2
    while path.exists():
        path = dest_dir / f"{base}-{n}{suffix}"
        n += 1
    return path


def _pg_env_and_url(url: str) -> tuple[dict, str]:
    """libpq URL (no '+psycopg' driver suffix); password passed via env, not argv."""
    u = make_url(url)
    env = dict(os.environ)
    if u.password:
        env["PGPASSWORD"] = u.password
    plain = u.set(drivername="postgresql", password=None).render_as_string(hide_password=False)
    return env, plain


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise BackupError(f"{tool} not found on PATH. Install the PostgreSQL client tools.")
    return path


def create_backup(url: str | None = None, dest_dir: Path | None = None) -> Path:
    url = url or settings.database_url
    dest_dir = dest_dir or backup_dir()
    backend = make_url(url).get_backend_name()
    if backend == "sqlite":
        src_path = _sqlite_path(url)
        if not src_path.exists():
            raise BackupError(f"Database file not found: {src_path}")
        dest = _new_path(dest_dir, ".sqlite3")
        src = sqlite3.connect(src_path)
        out = sqlite3.connect(dest)
        try:
            src.backup(out)  # consistent snapshot even while the shop is writing
        finally:
            out.close()
            src.close()
        return dest
    if backend == "postgresql":
        env, plain = _pg_env_and_url(url)
        dest = _new_path(dest_dir, ".pgdump")
        r = subprocess.run([_require("pg_dump"), "--format=custom", "--no-owner", f"--file={dest}", plain],
                           env=env, capture_output=True, text=True)
        if r.returncode != 0:
            dest.unlink(missing_ok=True)
            raise BackupError(f"pg_dump failed: {r.stderr.strip()}")
        return dest
    raise BackupError(f"Unsupported database: {backend}")


def verify_backup(path: Path) -> dict:
    """Restore the backup into a throwaway copy and check it. Returns row counts."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        raise BackupError(f"Backup missing or empty: {path}")
    if path.suffix == ".sqlite3":
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "restore-test.sqlite3"
            shutil.copyfile(path, copy)
            con = sqlite3.connect(copy)
            try:
                ok = con.execute("PRAGMA integrity_check").fetchone()[0]
                if ok != "ok":
                    raise BackupError(f"Integrity check failed: {ok}")
                counts = {}
                for t in KEY_TABLES:
                    try:
                        counts[t] = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                    except sqlite3.OperationalError as exc:
                        raise BackupError(f"Table {t} missing from backup") from exc
                return counts
            finally:
                con.close()
    if path.suffix == ".pgdump":
        r = subprocess.run([_require("pg_restore"), "--list", str(path)], capture_output=True, text=True)
        if r.returncode != 0:
            raise BackupError(f"pg_restore could not read the backup: {r.stderr.strip()}")
        missing = [t for t in KEY_TABLES if f"TABLE DATA public {t} " not in r.stdout]
        if missing:
            raise BackupError(f"Tables missing from backup: {', '.join(missing)}")
        return {t: "present" for t in KEY_TABLES}
    raise BackupError(f"Unknown backup type: {path.name}")


def restore_sqlite(path: Path, url: str | None = None) -> Path:
    """Replace the SQLite database with a backup. Takes a safety backup first."""
    url = url or settings.database_url
    if make_url(url).get_backend_name() != "sqlite":
        raise BackupError("Automatic restore is SQLite-only. For PostgreSQL use: pg_restore --clean --dbname=URL FILE")
    verify_backup(path)
    target = _sqlite_path(url)
    safety = create_backup(url) if target.exists() else None
    src = sqlite3.connect(path)
    out = sqlite3.connect(target)
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()
    return safety


def list_backups() -> list[Path]:
    d = backup_dir()
    return sorted([*d.glob("novahaus-*.sqlite3"), *d.glob("novahaus-*.pgdump")], key=lambda p: p.name)


def prune(keep: int) -> list[Path]:
    if keep < 1:
        raise BackupError("--keep must be at least 1")
    old = list_backups()[:-keep]
    for p in old:
        p.unlink()
    return old


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.backup", description="Back up and verify the shop database.")
    ap.add_argument("--list", action="store_true", help="list backups")
    ap.add_argument("--verify", metavar="FILE", help="verify an existing backup")
    ap.add_argument("--restore", metavar="FILE", help="restore a backup (SQLite only; needs --yes)")
    ap.add_argument("--yes", action="store_true", help="confirm --restore")
    ap.add_argument("--keep", type=int, metavar="N", help="after backing up, keep only the newest N backups")
    args = ap.parse_args(argv)
    try:
        if args.list:
            for p in list_backups():
                print(f"{p.name}  {p.stat().st_size / 1024:.0f} KB")
            return 0
        if args.verify:
            counts = verify_backup(Path(args.verify))
            print(f"OK: {args.verify} restores cleanly. Rows: {counts}")
            return 0
        if args.restore:
            if not args.yes:
                print("This replaces the current database. Stop the shop first, then re-run with --yes.")
                return 2
            safety = restore_sqlite(Path(args.restore))
            print(f"Restored {args.restore}." + (f" Previous database saved as {safety.name}." if safety else ""))
            return 0
        path = create_backup()
        counts = verify_backup(path)
        print(f"Backup saved: {path}")
        print(f"Verified: restores cleanly. Rows: {counts}")
        if args.keep:
            removed = prune(args.keep)
            if removed:
                print(f"Removed {len(removed)} older backup(s) (--keep {args.keep}).")
        return 0
    except BackupError as exc:
        print(f"BACKUP FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

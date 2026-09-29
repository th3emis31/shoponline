import os
import shutil
import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import backup
from app.db import Base
from app.models import Product
from app.seed import seed


@pytest.fixture()
def sqlite_db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'shop.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        seed(s)
    engine.dispose()
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(backup.settings, "database_url", url)
    return url, tmp_path / "shop.db"


def test_backup_and_verify(sqlite_db):
    path = backup.create_backup()
    assert path.exists() and path.suffix == ".sqlite3"
    counts = backup.verify_backup(path)
    assert counts["products"] == 5


def test_corrupt_or_empty_backup_is_rejected(sqlite_db, tmp_path):
    empty = tmp_path / "backups" / "novahaus-empty.sqlite3"
    empty.parent.mkdir(exist_ok=True)
    empty.write_bytes(b"")
    with pytest.raises(backup.BackupError, match="empty"):
        backup.verify_backup(empty)
    junk = tmp_path / "backups" / "novahaus-junk.sqlite3"
    junk.write_bytes(b"not a database" * 100)
    with pytest.raises(Exception):
        backup.verify_backup(junk)


def test_backups_in_the_same_second_never_overwrite(sqlite_db, monkeypatch):
    monkeypatch.setattr(backup, "_stamp", lambda: "20260101-000000")
    a, b = backup.create_backup(), backup.create_backup()
    assert a != b and a.exists() and b.exists()


def test_restore_brings_data_back_and_keeps_safety_copy(sqlite_db):
    url, db_file = sqlite_db
    good = backup.create_backup()
    con = sqlite3.connect(db_file)
    con.execute("DELETE FROM products")  # simulate an accident
    con.commit()
    con.close()
    safety = backup.restore_sqlite(good)
    con = sqlite3.connect(db_file)
    assert con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 5
    con.close()
    assert safety.exists()  # the damaged state was preserved too, nothing lost


def test_nothing_deleted_unless_keep_is_given(sqlite_db, monkeypatch):
    stamps = iter(["20260101-000000", "20260102-000000", "20260103-000000"])
    monkeypatch.setattr(backup, "_stamp", lambda: next(stamps))
    for _ in range(3):
        backup.create_backup()
    assert len(backup.list_backups()) == 3
    removed = backup.prune(2)
    assert [p.name for p in removed] == ["novahaus-20260101-000000.sqlite3"]
    assert len(backup.list_backups()) == 2
    with pytest.raises(backup.BackupError):
        backup.prune(0)


def test_cli(sqlite_db, capsys):
    assert backup.main([]) == 0
    out = capsys.readouterr().out
    assert "Backup saved" in out and "restores cleanly" in out
    assert backup.main(["--restore", str(backup.list_backups()[0])]) == 2  # refuses without --yes
    assert backup.main(["--verify", "/nope/missing.sqlite3"]) == 1


@pytest.mark.skipif(not shutil.which("pg_dump") or not os.environ.get("TEST_DATABASE_URL"),
                    reason="PostgreSQL backup test needs TEST_DATABASE_URL and pg_dump")
def test_postgres_backup_roundtrip(db, tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
    path = backup.create_backup(os.environ["TEST_DATABASE_URL"])
    assert path.suffix == ".pgdump"
    assert backup.verify_backup(path)["products"] == "present"

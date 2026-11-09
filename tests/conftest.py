import os
import re
import subprocess
from pathlib import Path

import pytest

from sakila_sync.cli import main
from sakila_sync.db import Databases

ROOT = Path(__file__).resolve().parent.parent
TEST_DB = os.environ.get("MYSQL_TEST_DATABASE", "sakila_test")
CONTAINER = "sakila-mysql"


def reset_test_database() -> None:
    """Recreate sakila_test from the official dump.

    Raw SQL: the dump creates tables, views, triggers and stored routines, which the
    ORM cannot do, so it is piped into the mysql client inside the Docker container.
    """
    if TEST_DB == os.environ.get("MYSQL_DATABASE", "sakila"):
        raise RuntimeError("MYSQL_TEST_DATABASE must differ from MYSQL_DATABASE; tests modify it.")
    sql = "\n".join((ROOT / "sql" / name).read_text(encoding="utf-8")
                    for name in ("sakila-schema.sql", "sakila-data.sql"))
    sql = re.sub(r"\bsakila\b", TEST_DB, sql)
    env = dict(os.environ, MYSQL_PWD=os.environ["MYSQL_PASSWORD"])
    subprocess.run(["docker", "exec", "-i", "-e", "MYSQL_PWD", CONTAINER, "mysql", "-uroot"],
                   input=sql.encode("utf-8"), env=env, check=True, capture_output=True)


@pytest.fixture(scope="session", autouse=True)
def fresh_sakila_test():
    reset_test_database()


@pytest.fixture
def dbs(tmp_path, monkeypatch):
    """Point every command at sakila_test and at a fresh SQLite file for this test."""
    monkeypatch.setenv("MYSQL_DATABASE", TEST_DB)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "analytics.db"))
    databases = Databases()
    yield databases
    databases.dispose()


@pytest.fixture
def loaded(dbs):
    assert main(["init"]) == 0
    assert main(["full-load"]) == 0
    return dbs

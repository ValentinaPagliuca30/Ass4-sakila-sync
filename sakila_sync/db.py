from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import mysql_url, sqlite_url


class Databases:
    """One engine and one session factory per database: MySQL is the source, SQLite the target."""

    def __init__(self, source_db: Optional[str] = None, target_path: Optional[str] = None):
        self.source_engine = create_engine(mysql_url(source_db))
        self.target_engine = create_engine(sqlite_url(target_path))
        self.SourceSession = sessionmaker(self.source_engine)
        self.TargetSession = sessionmaker(self.target_engine)

    def dispose(self) -> None:
        self.source_engine.dispose()
        self.target_engine.dispose()

import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv(override=False)
class ConfigError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing environment variable {name}. See .env.example.")
    return value


def mysql_url(database: Optional[str] = None) -> URL:
    
    return URL.create(
        "mysql+pymysql",
        username=_require("MYSQL_USER"),
        password=_require("MYSQL_PASSWORD"),
        host=_require("MYSQL_HOST"),
        port=int(_require("MYSQL_PORT")),
        database=database or _require("MYSQL_DATABASE"),
    )


def sqlite_url(path: Optional[str] = None) -> URL:
    return URL.create("sqlite", database=path or _require("SQLITE_PATH"))

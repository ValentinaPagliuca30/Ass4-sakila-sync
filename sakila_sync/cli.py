import argparse
import datetime as dt
import logging
import sys
from typing import List, Optional

from sqlalchemy.exc import SQLAlchemyError

from .config import ConfigError
from .db import Databases
from .init_db import run_init
from .sync import SyncError, run_sync
from .validate import ValidationError, run_validate

log = logging.getLogger("sakila_sync")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sakila_sync", description="Sakila -> SQLite analytics sync")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="create the SQLite schema, check MySQL, prepare dim_date and sync_state")
    commands.add_parser("full-load", help="load all source data, then validate")
    commands.add_parser("incremental", help="load rows changed since the last sync, then validate")
    validate = commands.add_parser("validate", help="compare MySQL and SQLite over a period")
    validate.add_argument("--from", dest="date_from", type=dt.date.fromisoformat, metavar="YYYY-MM-DD")
    validate.add_argument("--to", dest="date_to", type=dt.date.fromisoformat, metavar="YYYY-MM-DD")
    return parser


def run_command(dbs: Databases, args: argparse.Namespace) -> None:
    if args.command == "init":
        run_init(dbs)
    elif args.command == "full-load":
        run_sync(dbs, full=True)
        run_validate(dbs)
    elif args.command == "incremental":
        run_sync(dbs, full=False)
        run_validate(dbs)
    elif args.command == "validate":
        run_validate(dbs, args.date_from, args.date_to)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

    dbs = None
    try:
        dbs = Databases()
        run_command(dbs, args)
    except (ConfigError, SyncError, ValidationError) as exc:
        log.error("%s failed: %s", args.command, exc)
        return 1
    except SQLAlchemyError as exc:
        log.error("%s failed: database error: %s", args.command, getattr(exc, "orig", None) or exc)
        return 1
    except Exception:
        log.exception("%s failed with an unexpected error", args.command)
        return 1
    finally:
        if dbs is not None:
            dbs.dispose()

    log.info("%s completed successfully", args.command)
    return 0


if __name__ == "__main__":
    sys.exit(main())

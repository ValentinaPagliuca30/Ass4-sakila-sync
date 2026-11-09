import logging

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert

from .dates import calendar, ensure_dates
from .db import Databases
from .source_models import Film, Payment, Rental, SakilaBase
from .target_models import AnalyticsBase, SyncState

log = logging.getLogger(__name__)

SOURCE_TABLES = sorted(SakilaBase.metadata.tables)


def run_init(dbs: Databases) -> None:
    with dbs.SourceSession() as source:
        films = source.scalar(select(func.count()).select_from(Film))
        first_day = source.scalar(select(func.min(Rental.rental_date)))
        last_day = max(
            source.scalar(select(func.max(Rental.rental_date))),
            source.scalar(select(func.max(Rental.return_date))),
            source.scalar(select(func.max(Payment.payment_date))),
        )
        first_payment = source.scalar(select(func.min(Payment.payment_date)))
        first_day = min(first_day, first_payment)
    log.info("MySQL connection OK (%s, %d films)", dbs.source_engine.url.database, films)

    AnalyticsBase.metadata.create_all(dbs.target_engine)
    log.info("SQLite tables ready: %s", ", ".join(sorted(AnalyticsBase.metadata.tables)))

    days = calendar(first_day.date(), last_day.date())
    with dbs.TargetSession.begin() as target:
        ensure_dates(target, days)

        target.execute(
            insert(SyncState)
            .values([{"table_name": t, "last_update": None} for t in SOURCE_TABLES])
            .on_conflict_do_nothing()
        )
    log.info("dim_date covers %s to %s (%d days)", days[0], days[-1], len(days))
    log.info("sync_state prepared for %d source tables", len(SOURCE_TABLES))

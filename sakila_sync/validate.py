import datetime as dt
import logging
from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy import func, select

from .dates import date_key
from .db import Databases
from .source_models import (
    Actor, Category, Customer, Film, FilmActor, FilmCategory, Inventory, Payment, Rental, Staff, Store,
)
from .target_models import (
    BridgeFilmActor, BridgeFilmCategory, DimActor, DimCategory, DimCustomer, DimDate, DimFilm,
    DimStore, FactPayment, FactRental,
)

log = logging.getLogger(__name__)

TOLERANCE = Decimal("0.01")

COUNT_PAIRS = [
    (Film, DimFilm), (Actor, DimActor), (Category, DimCategory), (Store, DimStore),
    (Customer, DimCustomer), (FilmActor, BridgeFilmActor), (FilmCategory, BridgeFilmCategory),
    (Rental, FactRental), (Payment, FactPayment),
]

NATURAL_KEYS = [
    (DimFilm, DimFilm.film_id), (DimActor, DimActor.actor_id), (DimCategory, DimCategory.category_id),
    (DimStore, DimStore.store_id), (DimCustomer, DimCustomer.customer_id), (DimDate, DimDate.date),
    (FactRental, FactRental.rental_id), (FactPayment, FactPayment.payment_id),
]

FACT_REFERENCES = [
    (FactRental.date_key_rented, DimDate.date_key), (FactRental.date_key_returned, DimDate.date_key),
    (FactRental.film_key, DimFilm.film_key), (FactRental.store_key, DimStore.store_key),
    (FactRental.customer_key, DimCustomer.customer_key),
    (FactPayment.date_key_paid, DimDate.date_key), (FactPayment.customer_key, DimCustomer.customer_key),
    (FactPayment.store_key, DimStore.store_key),
    (BridgeFilmActor.film_key, DimFilm.film_key), (BridgeFilmActor.actor_key, DimActor.actor_key),
    (BridgeFilmCategory.film_key, DimFilm.film_key), (BridgeFilmCategory.category_key, DimCategory.category_key),
]

class ValidationError(RuntimeError):
    pass

def default_period(dbs: Databases) -> Tuple[dt.date, dt.date]:
    """The 30 days ending on the latest payment date in Sakila."""
    with dbs.SourceSession() as source:
        last = source.scalar(select(func.max(Payment.payment_date))).date()
    return last - dt.timedelta(days=29), last


def run_validate(dbs: Databases, date_from: Optional[dt.date] = None, date_to: Optional[dt.date] = None) -> None:
    if date_from is None or date_to is None:
        default_from, default_to = default_period(dbs)
        date_from = date_from or default_from
        date_to = date_to or default_to
    if date_from > date_to:
        raise ValidationError(f"--from {date_from} is after --to {date_to}")
    log.info("validating period %s to %s", date_from, date_to)
    start, end = dt.datetime.combine(date_from, dt.time()), dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time())
    key_from, key_to = date_key(date_from), date_key(date_to)
    errors = []

    def check(ok: bool, message: str) -> None:
        if ok:
            log.info("OK      %s", message)
        else:
            log.error("MISMATCH %s", message)
            errors.append(message)

    with dbs.SourceSession() as source, source.begin(), dbs.TargetSession() as target:
        for src_model, tgt_model in COUNT_PAIRS:
            s = source.scalar(select(func.count()).select_from(src_model))
            t = target.scalar(select(func.count()).select_from(tgt_model))
            check(s == t, f"rows {src_model.__tablename__}={s} vs {tgt_model.__tablename__}={t}")
        src_rentals = dict(source.execute(
            select(Inventory.store_id, func.count())
            .select_from(Rental)
            .join(Inventory, Rental.inventory_id == Inventory.inventory_id)
            .where(Rental.rental_date >= start, Rental.rental_date < end)
            .group_by(Inventory.store_id)).all())
        tgt_rentals = dict(target.execute(
            select(DimStore.store_id, func.count())
            .select_from(FactRental)
            .join(DimStore, FactRental.store_key == DimStore.store_key)
            .where(FactRental.date_key_rented.between(key_from, key_to))
            .group_by(DimStore.store_id)).all())
        for store in sorted(set(src_rentals) | set(tgt_rentals)):
            s, t = src_rentals.get(store, 0), tgt_rentals.get(store, 0)
            check(s == t, f"rentals in period, store {store}: {s} vs {t}")
        store_id = func.coalesce(Inventory.store_id, Staff.store_id)
        src_pay = {sid: (n, amount) for sid, n, amount in source.execute(
            select(store_id, func.count(), func.sum(Payment.amount))
            .select_from(Payment)
            .outerjoin(Rental, Payment.rental_id == Rental.rental_id)
            .outerjoin(Inventory, Rental.inventory_id == Inventory.inventory_id)
            .join(Staff, Payment.staff_id == Staff.staff_id)
            .where(Payment.payment_date >= start, Payment.payment_date < end)
            .group_by(store_id))}
        tgt_pay = {sid: (n, amount) for sid, n, amount in target.execute(
            select(DimStore.store_id, func.count(), func.sum(FactPayment.amount))
            .select_from(FactPayment)
            .join(DimStore, FactPayment.store_key == DimStore.store_key)
            .where(FactPayment.date_key_paid.between(key_from, key_to))
            .group_by(DimStore.store_id))}
        for store in sorted(set(src_pay) | set(tgt_pay)):
            s_n, s_amt = src_pay.get(store, (0, 0))
            t_n, t_amt = tgt_pay.get(store, (0, 0))
            check(s_n == t_n, f"payments in period, store {store}: {s_n} vs {t_n}")
            diff = abs(Decimal(str(s_amt or 0)) - Decimal(str(t_amt or 0)))
            check(diff <= TOLERANCE, f"amount in period, store {store}: {s_amt} vs {t_amt} (diff {diff})")
        for name, src_id, src_date, tgt_id in [
            ("rental", Rental.rental_id, Rental.rental_date, FactRental.rental_id),
            ("payment", Payment.payment_id, Payment.payment_date, FactPayment.payment_id),
        ]:
            src_ids = set(source.scalars(select(src_id).where(src_date >= start, src_date < end)))
            missing = src_ids - set(target.scalars(select(tgt_id)))
            check(not missing, f"missing {name} rows in SQLite: {len(missing)} {sorted(missing)[:10]}")

        for model, column in NATURAL_KEYS:
            dupes = target.scalar(select(func.count()).select_from(
                select(column).group_by(column).having(func.count() > 1).subquery()))
            check(dupes == 0, f"duplicate {model.__tablename__}.{column.key}: {dupes}")

        for fk, pk in FACT_REFERENCES:
            orphans = target.scalar(
                select(func.count()).select_from(fk.table)
                .outerjoin(pk.table, fk == pk)
                .where(fk.isnot(None), pk.is_(None)))
            check(orphans == 0, f"orphan {fk.table.name}.{fk.key}: {orphans}")

    if errors:
        raise ValidationError(f"{len(errors)} check(s) failed")
    log.info("all checks passed")

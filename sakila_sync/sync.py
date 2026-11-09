"""full-load + incremental 

"""
import logging
from typing import Dict, List, Optional

from sqlalchemy import func, or_, select, true
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from .dates import date_key, ensure_dates
from .db import Databases
from .source_models import (
    Actor, Address, Category, City, Country, Customer, Film, FilmActor, FilmCategory,
    Inventory, Language, Payment, Rental, Staff, Store,
)
from .target_models import (
    BridgeFilmActor, BridgeFilmCategory, DimActor, DimCategory, DimCustomer, DimFilm,
    DimStore, FactPayment, FactRental, SyncState,
)

log = logging.getLogger(__name__)

# SQLite's limit on bound parameters per statement
CHUNK = 1000

SOURCE_MODELS = {m.__tablename__: m for m in (
    Actor, Address, Category, City, Country, Customer, Film, FilmActor, FilmCategory,
    Inventory, Language, Payment, Rental, Staff, Store,
)}


class SyncError(RuntimeError):
    pass


def changed_since(markers: Optional[Dict], *models):
    """WHERE condition: any of the given source tables changed since its marker."""
    if markers is None:
        return true()
    return or_(*(m.last_update >= markers[m.__tablename__] for m in models))


def upsert(target: Session, model, rows: List[dict], keys: List[str]) -> None:
    """Insert rows, or overwrite the existing row with the same natural key (Type 1)."""
    for start in range(0, len(rows), CHUNK):
        stmt = insert(model).values(rows[start:start + CHUNK])
        update_cols = {c: stmt.excluded[c] for c in rows[0] if c not in keys}
        if update_cols:
            stmt = stmt.on_conflict_do_update(index_elements=keys, set_=update_cols)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=keys)
        target.execute(stmt)


def key_map(target: Session, natural, surrogate) -> Dict[int, int]:
    """natural key -> surrogate key, e.g. {film_id: film_key}."""
    return dict(target.execute(select(natural, surrogate)).all())


# Dim

def load_dim_film(source, target, markers) -> int:
    q = (select(Film, Language.name)
         .join(Language, Film.language_id == Language.language_id)
         .where(changed_since(markers, Film, Language)))
    rows = [{"film_id": f.film_id, "title": f.title, "rating": f.rating, "length": f.length,
             "language": lang.strip(), "release_year": f.release_year, "last_update": f.last_update}
            for f, lang in source.execute(q)]
    upsert(target, DimFilm, rows, ["film_id"])
    return len(rows)


def load_dim_actor(source, target, markers) -> int:
    q = select(Actor).where(changed_since(markers, Actor))
    rows = [{"actor_id": a.actor_id, "first_name": a.first_name, "last_name": a.last_name,
             "last_update": a.last_update} for a in source.scalars(q)]
    upsert(target, DimActor, rows, ["actor_id"])
    return len(rows)


def load_dim_category(source, target, markers) -> int:
    q = select(Category).where(changed_since(markers, Category))
    rows = [{"category_id": c.category_id, "name": c.name, "last_update": c.last_update}
            for c in source.scalars(q)]
    upsert(target, DimCategory, rows, ["category_id"])
    return len(rows)


def load_dim_store(source, target, markers) -> int:
    q = (select(Store, City.city, Country.country)
         .join(Address, Store.address_id == Address.address_id)
         .join(City, Address.city_id == City.city_id)
         .join(Country, City.country_id == Country.country_id)
         .where(changed_since(markers, Store, Address, City, Country)))
    rows = [{"store_id": s.store_id, "city": city, "country": country, "last_update": s.last_update}
            for s, city, country in source.execute(q)]
    upsert(target, DimStore, rows, ["store_id"])
    return len(rows)


def load_dim_customer(source, target, markers) -> int:
    q = (select(Customer, City.city, Country.country)
         .join(Address, Customer.address_id == Address.address_id)
         .join(City, Address.city_id == City.city_id)
         .join(Country, City.country_id == Country.country_id)
         .where(changed_since(markers, Customer, Address, City, Country)))
    rows = [{"customer_id": c.customer_id, "first_name": c.first_name, "last_name": c.last_name,
             "active": bool(c.active), "city": city, "country": country, "last_update": c.last_update}
            for c, city, country in source.execute(q)]
    upsert(target, DimCustomer, rows, ["customer_id"])
    return len(rows)


# Bridge

def load_bridge_film_actor(source, target, markers) -> int:
    films = key_map(target, DimFilm.film_id, DimFilm.film_key)
    actors = key_map(target, DimActor.actor_id, DimActor.actor_key)
    q = select(FilmActor).where(changed_since(markers, FilmActor))
    rows = [{"film_key": films[fa.film_id], "actor_key": actors[fa.actor_id]}
            for fa in source.scalars(q)]
    upsert(target, BridgeFilmActor, rows, ["film_key", "actor_key"])
    return len(rows)


def load_bridge_film_category(source, target, markers) -> int:
    films = key_map(target, DimFilm.film_id, DimFilm.film_key)
    categories = key_map(target, DimCategory.category_id, DimCategory.category_key)
    q = select(FilmCategory).where(changed_since(markers, FilmCategory))
    rows = [{"film_key": films[fc.film_id], "category_key": categories[fc.category_id]}
            for fc in source.scalars(q)]
    upsert(target, BridgeFilmCategory, rows, ["film_key", "category_key"])
    return len(rows)


# Fact

def load_fact_rental(source, target, markers) -> int:
    q = (select(Rental, Inventory.film_id, Inventory.store_id)
         .join(Inventory, Rental.inventory_id == Inventory.inventory_id)
         .where(changed_since(markers, Rental, Inventory)))
    result = source.execute(q).all()

    days = [r.rental_date.date() for r, _, _ in result]
    days += [r.return_date.date() for r, _, _ in result if r.return_date]
    ensure_dates(target, days)

    films = key_map(target, DimFilm.film_id, DimFilm.film_key)
    stores = key_map(target, DimStore.store_id, DimStore.store_key)
    customers = key_map(target, DimCustomer.customer_id, DimCustomer.customer_key)
    rows = []
    for r, film_id, store_id in result:
        returned = r.return_date.date() if r.return_date else None
        rows.append({
            "rental_id": r.rental_id,
            "date_key_rented": date_key(r.rental_date.date()),
            "date_key_returned": date_key(returned),
            "film_key": films[film_id],
            "store_key": stores[store_id],
            "customer_key": customers[r.customer_id],
            "staff_id": r.staff_id,
            "rental_duration_days": (returned - r.rental_date.date()).days if returned else None,
        })
    upsert(target, FactRental, rows, ["rental_id"])
    return len(rows)


def load_fact_payment(source, target, markers) -> int:
    store_id = func.coalesce(Inventory.store_id, Staff.store_id)
    q = (select(Payment, store_id)
         .outerjoin(Rental, Payment.rental_id == Rental.rental_id)
         .outerjoin(Inventory, Rental.inventory_id == Inventory.inventory_id)
         .join(Staff, Payment.staff_id == Staff.staff_id)
         .where(changed_since(markers, Payment, Rental, Inventory, Staff)))
    result = source.execute(q).all()

    ensure_dates(target, [p.payment_date.date() for p, _ in result])

    stores = key_map(target, DimStore.store_id, DimStore.store_key)
    customers = key_map(target, DimCustomer.customer_id, DimCustomer.customer_key)
    rows = [{"payment_id": p.payment_id,
             "date_key_paid": date_key(p.payment_date.date()),
             "customer_key": customers[p.customer_id],
             "store_key": stores[sid],
             "staff_id": p.staff_id,
             "amount": p.amount} for p, sid in result]
    upsert(target, FactPayment, rows, ["payment_id"])
    return len(rows)



STEPS = [
    ("dim_film", load_dim_film),
    ("dim_actor", load_dim_actor),
    ("dim_category", load_dim_category),
    ("dim_store", load_dim_store),
    ("dim_customer", load_dim_customer),
    ("bridge_film_actor", load_bridge_film_actor),
    ("bridge_film_category", load_bridge_film_category),
    ("fact_rental", load_fact_rental),
    ("fact_payment", load_fact_payment),
]


def read_markers(target: Session) -> Dict:
    return dict(target.execute(select(SyncState.table_name, SyncState.last_update)).all())


def source_maxima(source: Session) -> Dict:
    """Latest last_update per source table, read in the same snapshot as the data."""
    return {name: source.scalar(select(func.max(m.last_update))) for name, m in SOURCE_MODELS.items()}


def run_sync(dbs: Databases, full: bool) -> None:
    mode = "full-load" if full else "incremental"
    with dbs.SourceSession() as source, source.begin(), dbs.TargetSession.begin() as target:
        stored = read_markers(target)
        if not stored:
            raise SyncError("sync_state is empty. Run init first.")
        if full:
            markers = None
        else:
            never_synced = sorted(t for t, v in stored.items() if v is None)
            if never_synced:
                raise SyncError(f"no marker for {', '.join(never_synced)}. Run full-load first.")
            markers = stored
            log.info("reading rows with last_update >= markers (oldest marker: %s)", min(stored.values()))

        new_markers = source_maxima(source)
        for name, step in STEPS:
            log.info("%-21s %6d rows upserted", name, step(source, target, markers))

        for table, value in new_markers.items():
            if value is not None:
                target.merge(SyncState(table_name=table, last_update=value))
    log.info("%s committed; markers saved for %d tables", mode, len(new_markers))

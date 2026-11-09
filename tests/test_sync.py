import datetime as dt
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, inspect, select

from sakila_sync.cli import main
from sakila_sync.source_models import Address, City, Country, Customer, Payment, Rental
from sakila_sync.target_models import (
    AnalyticsBase, DimCustomer, DimDate, DimFilm, DimStore, FactPayment, FactRental, SyncState,
)
from sakila_sync.validate import COUNT_PAIRS


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def rental_fact(target, rental_id):
    return target.scalars(select(FactRental).where(FactRental.rental_id == rental_id)).one()


def payment_store(target, payment_id):
    return target.scalar(select(DimStore.store_id)
                         .join(FactPayment, FactPayment.store_key == DimStore.store_key)
                         .where(FactPayment.payment_id == payment_id))


def test_init_creates_database_and_tables(dbs):
    assert main(["init"]) == 0

    assert Path(dbs.target_engine.url.database).exists()
    assert set(inspect(dbs.target_engine).get_table_names()) == set(AnalyticsBase.metadata.tables)
    with dbs.TargetSession() as target:
        assert count(target, DimDate) > 0
        assert count(target, SyncState) == 15


def test_full_load_copies_all_data(loaded):
    with loaded.SourceSession() as source, loaded.TargetSession() as target:
        for src_model, tgt_model in COUNT_PAIRS:
            assert count(source, src_model) == count(target, tgt_model), tgt_model.__tablename__

        film = target.scalars(select(DimFilm).where(DimFilm.film_id == 141)).one()
        assert (film.title, film.rating, film.length, film.language) == ("CHICAGO NORTH", "PG-13", 185, "English")
        returned = rental_fact(target, 3818)
        assert (returned.date_key_rented, returned.date_key_returned, returned.rental_duration_days) == (20050706, 20050711, 5)
        not_returned = rental_fact(target, 11496)
        assert not_returned.date_key_returned is None and not_returned.rental_duration_days is None

        assert target.scalar(select(func.count()).where(SyncState.last_update.is_(None))) == 0


def test_incremental_picks_up_new_rows(loaded):
    with loaded.SourceSession.begin() as source:
        rental =Rental(rental_date=dt.datetime(2006, 3, 1, 10, 0), inventory_id=1, customer_id=1, staff_id=1)
        source.add(rental)
        source.flush()
        #  staff 2 works at store 2, but the copy is in store 1
        paid = Payment(customer_id=1, staff_id=2, rental_id=rental.rental_id, amount=Decimal("3.99"),
                       payment_date=dt.datetime(2006, 3, 1, 10, 5))
        no_rental = Payment(customer_id=1, staff_id=2, rental_id=None, amount=Decimal("1.50"),
                            payment_date=dt.datetime(2006, 3, 1, 11, 0))
        source.add_all([paid, no_rental])
        source.flush()

        # sakila triggers set rental_date and payment_date to now() on insert, so we set them again with an update
        for row in (rental, paid, no_rental):
            source.refresh(row)
        rental.rental_date = dt.datetime(2006, 3, 1, 10, 0)
        paid.payment_date = dt.datetime(2006, 3, 1, 10, 5)
        no_rental.payment_date = dt.datetime(2006, 3, 1, 11, 0)
        ids = rental.rental_id, paid.payment_id, no_rental.payment_id
    rental_id, paid_id, no_rental_id = ids

    assert main(["incremental"]) == 0

    with loaded.TargetSession() as target:
        fact = rental_fact(target, rental_id)
        assert fact.date_key_rented == 20060301 and fact.date_key_returned is None
        assert target.get(DimDate, 20060301).day_of_week == 3
        assert payment_store(target, paid_id) == 1
        assert payment_store(target, no_rental_id) == 2
        rentals_before = count(target, FactRental)

    assert main(["incremental"]) == 0
    with loaded.TargetSession() as target:
        assert count(target, FactRental) == rentals_before


def test_incremental_applies_updates(loaded):
    with loaded.SourceSession.begin() as source:
        source.get(Rental, 11496).return_date = dt.datetime(2006, 2, 20, 9, 0)
        # customer 97 moves to another existing addres
        source.get(Customer, 97).address_id = 5
        # only the city row changes for customer 155
        city_155 = source.scalar(select(City).join(Address, Address.city_id == City.city_id)
                                 .join(Customer, Customer.address_id == Address.address_id)
                                 .where(Customer.customer_id == 155))
        city_155.city = "Renamed City"
        expected_97 = source.execute(select(City.city, Country.country)
                                     .join(Address, Address.city_id == City.city_id)
                                     .join(Country, City.country_id == Country.country_id)
                                     .where(Address.address_id == 5)).one()

    assert main(["incremental"]) == 0

    with loaded.TargetSession() as target:
        fact = rental_fact(target, 11496)
        assert (fact.date_key_returned, fact.rental_duration_days) == (20060220, 6)
        moved = target.scalars(select(DimCustomer).where(DimCustomer.customer_id == 97)).one()
        assert (moved.city, moved.country) == tuple(expected_97)
        renamed = target.scalars(select(DimCustomer).where(DimCustomer.customer_id == 155)).one()
        assert renamed.city == "Renamed City"


def test_validate_passes_then_reports_mismatch(loaded, caplog):
    assert main(["validate"]) == 0

    with loaded.TargetSession.begin() as target:
        latest = target.scalars(select(FactPayment).order_by(FactPayment.date_key_paid.desc())).first()
        latest.amount += Decimal("1.00")

    assert main(["validate"]) == 1
    assert "MISMATCH amount in period" in caplog.text

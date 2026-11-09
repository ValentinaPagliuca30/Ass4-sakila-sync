"""
*_key columns are surrogate keys assigned by SQLite
*_id columns are the natural keys copied from Sakila; their unique indexes are 
the conflict targets of every upsert
"""
import datetime as dt
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AnalyticsBase(DeclarativeBase):
    pass

class DimDate(AnalyticsBase):
    __tablename__ = "dim_date"
    date_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    date: Mapped[dt.date] = mapped_column(Date, unique=True)
    year: Mapped[int] = mapped_column(Integer)
    quarter: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    day_of_month: Mapped[int] = mapped_column(Integer)
    day_of_week: Mapped[int] = mapped_column(Integer)
    is_weekend: Mapped[bool] = mapped_column(Boolean)


class DimFilm(AnalyticsBase):
    __tablename__ = "dim_film"
    film_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    film_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(128))
    rating: Mapped[Optional[str]] = mapped_column(String(5))
    length: Mapped[Optional[int]] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(20))
    release_year: Mapped[Optional[int]] = mapped_column(Integer)
    last_update: Mapped[dt.datetime] = mapped_column(DateTime)

    __table_args__ = (Index("ux_dim_film_film_id", "film_id", unique=True),)


class DimActor(AnalyticsBase):
    __tablename__ = "dim_actor"
    actor_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(Integer)
    first_name: Mapped[str] = mapped_column(String(45))
    last_name: Mapped[str] = mapped_column(String(45))
    last_update: Mapped[dt.datetime] = mapped_column(DateTime)

    __table_args__ = (Index("ux_dim_actor_actor_id", "actor_id", unique=True),)


class DimCategory(AnalyticsBase):
    __tablename__ = "dim_category"
    category_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(25))
    last_update: Mapped[dt.datetime] = mapped_column(DateTime)

    __table_args__ = (Index("ux_dim_category_category_id", "category_id", unique=True),)


class DimStore(AnalyticsBase):
    __tablename__ = "dim_store"
    store_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(Integer)
    city: Mapped[str] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(50))
    last_update: Mapped[dt.datetime] = mapped_column(DateTime)

    __table_args__ = (Index("ux_dim_store_store_id", "store_id", unique=True),)


class DimCustomer(AnalyticsBase):
    __tablename__ = "dim_customer"
    customer_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer)
    first_name: Mapped[str] = mapped_column(String(45))
    last_name: Mapped[str] = mapped_column(String(45))
    active: Mapped[bool] = mapped_column(Boolean)
    city: Mapped[str] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(50))
    last_update: Mapped[dt.datetime] = mapped_column(DateTime)

    __table_args__ = (Index("ux_dim_customer_customer_id", "customer_id", unique=True),)


class BridgeFilmActor(AnalyticsBase):
    __tablename__ = "bridge_film_actor"
    # composite primary key
    film_key: Mapped[int] = mapped_column(ForeignKey("dim_film.film_key"), primary_key=True)
    actor_key: Mapped[int] = mapped_column(ForeignKey("dim_actor.actor_key"), primary_key=True)


class BridgeFilmCategory(AnalyticsBase):
    __tablename__ = "bridge_film_category"
    film_key: Mapped[int] = mapped_column(ForeignKey("dim_film.film_key"), primary_key=True)
    category_key: Mapped[int] = mapped_column(ForeignKey("dim_category.category_key"), primary_key=True)


class FactRental(AnalyticsBase):
    __tablename__ = "fact_rental"
    fact_rental_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    rental_id: Mapped[int] = mapped_column(Integer)
    date_key_rented: Mapped[int] = mapped_column(ForeignKey("dim_date.date_key"))
    date_key_returned: Mapped[Optional[int]] = mapped_column(ForeignKey("dim_date.date_key"))
    film_key: Mapped[int] = mapped_column(ForeignKey("dim_film.film_key"))
    store_key: Mapped[int] = mapped_column(ForeignKey("dim_store.store_key"))
    customer_key: Mapped[int] = mapped_column(ForeignKey("dim_customer.customer_key"))
    staff_id: Mapped[int] = mapped_column(Integer)
    rental_duration_days: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (
        Index("ux_fact_rental_rental_id", "rental_id", unique=True),
        Index("ix_fact_rental_date_key_rented", "date_key_rented"),
        Index("ix_fact_rental_date_key_returned", "date_key_returned"),
        Index("ix_fact_rental_film_key", "film_key"),
        Index("ix_fact_rental_store_key", "store_key"),
        Index("ix_fact_rental_customer_key", "customer_key"),
    )


class FactPayment(AnalyticsBase):
    __tablename__ = "fact_payment"
    fact_payment_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(Integer)
    date_key_paid: Mapped[int] = mapped_column(ForeignKey("dim_date.date_key"))
    customer_key: Mapped[int] = mapped_column(ForeignKey("dim_customer.customer_key"))
    store_key: Mapped[int] = mapped_column(ForeignKey("dim_store.store_key"))
    staff_id: Mapped[int] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(5, 2))

    __table_args__ = (
        Index("ux_fact_payment_payment_id", "payment_id", unique=True),
        Index("ix_fact_payment_date_key_paid", "date_key_paid"),
        Index("ix_fact_payment_customer_key", "customer_key"),
        Index("ix_fact_payment_store_key", "store_key"),
    )


class SyncState(AnalyticsBase):
    __tablename__ = "sync_state"
    table_name: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_update: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)


from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, FetchedValue, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SakilaBase(DeclarativeBase):
    pass


def last_update_column() -> Mapped[datetime]:
    return mapped_column(DateTime, server_default=FetchedValue(), server_onupdate=FetchedValue())


class Country(SakilaBase):
    __tablename__ = "country"
    country_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country: Mapped[str] = mapped_column(String(50))
    last_update: Mapped[datetime] = last_update_column()


class City(SakilaBase):
    __tablename__ = "city"
    city_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String(50))
    country_id: Mapped[int] = mapped_column(ForeignKey("country.country_id"))
    last_update: Mapped[datetime] = last_update_column()


class Address(SakilaBase):
    __tablename__ = "address"
    address_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    address: Mapped[str] = mapped_column(String(50))
    district: Mapped[str] = mapped_column(String(20))
    city_id: Mapped[int] = mapped_column(ForeignKey("city.city_id"))
    postal_code: Mapped[Optional[str]] = mapped_column(String(10))
    phone: Mapped[str] = mapped_column(String(20))
    last_update: Mapped[datetime] = last_update_column()


class Language(SakilaBase):
    __tablename__ = "language"
    language_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20))
    last_update: Mapped[datetime] = last_update_column()


class Film(SakilaBase):
    __tablename__ = "film"
    film_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    release_year: Mapped[Optional[int]] = mapped_column(Integer)
    language_id: Mapped[int] = mapped_column(ForeignKey("language.language_id"))
    rental_duration: Mapped[int] = mapped_column(Integer, server_default=FetchedValue())
    rental_rate: Mapped[Decimal] = mapped_column(Numeric(4, 2), server_default=FetchedValue())
    length: Mapped[Optional[int]] = mapped_column(Integer)
    replacement_cost: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default=FetchedValue())
    rating: Mapped[Optional[str]] = mapped_column(String(5))
    last_update: Mapped[datetime] = last_update_column()


class Actor(SakilaBase):
    __tablename__ = "actor"
    actor_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(45))
    last_name: Mapped[str] = mapped_column(String(45))
    last_update: Mapped[datetime] = last_update_column()


class Category(SakilaBase):
    __tablename__ = "category"
    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(25))
    last_update: Mapped[datetime] = last_update_column()


class FilmActor(SakilaBase):
    __tablename__ = "film_actor"
    actor_id: Mapped[int] = mapped_column(ForeignKey("actor.actor_id"), primary_key=True)
    film_id: Mapped[int] = mapped_column(ForeignKey("film.film_id"), primary_key=True)
    last_update: Mapped[datetime] = last_update_column()


class FilmCategory(SakilaBase):
    __tablename__ = "film_category"
    film_id: Mapped[int] = mapped_column(ForeignKey("film.film_id"), primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.category_id"), primary_key=True)
    last_update: Mapped[datetime] = last_update_column()


class Store(SakilaBase):
    __tablename__ = "store"
    store_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manager_staff_id: Mapped[int] = mapped_column(ForeignKey("staff.staff_id"))
    address_id: Mapped[int] = mapped_column(ForeignKey("address.address_id"))
    last_update: Mapped[datetime] = last_update_column()


class Staff(SakilaBase):
    __tablename__ = "staff"
    staff_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(45))
    last_name: Mapped[str] = mapped_column(String(45))
    address_id: Mapped[int] = mapped_column(ForeignKey("address.address_id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("store.store_id"))
    active: Mapped[bool] = mapped_column(server_default=FetchedValue())
    username: Mapped[str] = mapped_column(String(16))
    last_update: Mapped[datetime] = last_update_column()


class Customer(SakilaBase):
    __tablename__ = "customer"
    customer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("store.store_id"))
    first_name: Mapped[str] = mapped_column(String(45))
    last_name: Mapped[str] = mapped_column(String(45))
    email: Mapped[Optional[str]] = mapped_column(String(50))
    address_id: Mapped[int] = mapped_column(ForeignKey("address.address_id"))
    active: Mapped[bool] = mapped_column(server_default=FetchedValue())
    create_date: Mapped[datetime] = mapped_column(DateTime)
    last_update: Mapped[datetime] = last_update_column()


class Inventory(SakilaBase):
    __tablename__ = "inventory"
    inventory_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    film_id: Mapped[int] = mapped_column(ForeignKey("film.film_id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("store.store_id"))
    last_update: Mapped[datetime] = last_update_column()


class Rental(SakilaBase):
    __tablename__ = "rental"
    rental_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rental_date: Mapped[datetime] = mapped_column(DateTime)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory.inventory_id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.customer_id"))
    return_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.staff_id"))
    last_update: Mapped[datetime] = last_update_column()


class Payment(SakilaBase):
    __tablename__ = "payment"
    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.customer_id"))
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.staff_id"))
    rental_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rental.rental_id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    payment_date: Mapped[datetime] = mapped_column(DateTime)
    last_update: Mapped[datetime] = last_update_column()

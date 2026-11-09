import datetime as dt
from typing import Iterable, List, Optional

from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from .target_models import DimDate


def date_key(value: Optional[dt.date]) -> Optional[int]:
    if value is None:
        return None
    return value.year * 10000 + value.month * 100 + value.day


def dim_date_row(day: dt.date) -> dict:
    iso_weekday = day.isoweekday()  # Monday = 1 ... Sunday = 7
    return {
        "date_key": date_key(day),
        "date": day,
        "year": day.year,
        "quarter": (day.month - 1) // 3 + 1,
        "month": day.month,
        "day_of_month": day.day,
        "day_of_week": iso_weekday,
        "is_weekend": iso_weekday >= 6,
    }


def calendar(first: dt.date, last: dt.date) -> List[dt.date]:
    return [first + dt.timedelta(days=i) for i in range((last - first).days + 1)]


def ensure_dates(session: Session, days: Iterable[dt.date]) -> None:
    """Insert the given days into dim_date, skipping those already present."""
    rows = [dim_date_row(d) for d in sorted(set(days))]
    if rows:
        # A date's attributes never change, so an existing row is left as is.
        session.execute(insert(DimDate).values(rows).on_conflict_do_nothing())

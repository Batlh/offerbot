"""Letzter gültiger Kalendertag regionaler Angebote."""
import re
from datetime import date


def end_date(value, found_at=""):
    value = (value or "").strip()
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value[:10])
        match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(?:(\d{2}|\d{4}))?", value)
        if not match:
            return None
        day, month = map(int, match.groups()[:2])
        if match[3]:
            year = int(match[3])
            return date(year + 2000 if year < 100 else year, month, day)
        anchor = date.fromisoformat(found_at[:10]) if found_at else date.today()
        year = anchor.year
        if month == 1 and anchor.month == 12:
            year += 1
        elif month == 12 and anchor.month == 1:
            year -= 1
        return date(year, month, day)
    except ValueError:
        return None


def active(value, found_at, today=None):
    end = end_date(value, found_at)
    return end is None or end >= (today or date.today())

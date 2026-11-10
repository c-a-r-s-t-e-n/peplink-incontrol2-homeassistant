"""Time-aware GPS utilities for current and historical Peplink locations."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_CURRENT_AGE = timedelta(minutes=30)


def timestamp_utc(timestamp, group_timezone="UTC"):
    """Parse an InControl timestamp, interpreting naive times in group timezone."""
    if not timestamp:
        return None
    try:
        date = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if date.tzinfo is None:
            date = date.replace(tzinfo=ZoneInfo(group_timezone or "UTC"))
        return date.astimezone(timezone.utc)
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        return None


def location_info(location, timezone_name="UTC", online=False, now=None):
    """Return a safe historical point with explicit freshness; never infer missing GPS."""
    if not isinstance(location, dict) or location.get("isStatic") is True:
        return None
    try:
        lat, lon = float(location["la"]), float(location["lo"])
    except (ValueError, TypeError, KeyError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    measured = timestamp_utc(location.get("ts"), timezone_name)
    if measured is None:
        return None
    current_time = now or datetime.now(timezone.utc)
    age = current_time - measured
    is_current = bool(online and -timedelta(minutes=5) <= age <= MAX_CURRENT_AGE)
    return {
        "latitude": lat,
        "longitude": lon,
        "measured_at": measured.isoformat(),
        "age_minutes": max(0, round(age.total_seconds() / 60, 1)),
        "is_current": is_current,
    }

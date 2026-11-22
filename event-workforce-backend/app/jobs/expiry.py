"""Time-aware job expiry helpers (all event times are interpreted in India Standard Time)."""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
HISTORY_STATUSES = {"expired", "completed", "cancelled"}


def job_is_expired(job: dict, now: datetime | None = None) -> bool:
    status = str(job.get("status") or "").lower()
    if status in HISTORY_STATUSES:
        return True
    raw_date = job.get("job_date")
    if not raw_date:
        return False
    try:
        event_date = raw_date if isinstance(raw_date, date) else date.fromisoformat(str(raw_date)[:10])
    except (TypeError, ValueError):
        return False

    # A job without an end/start time remains available until its reporting time.
    raw_time = job.get("end_time") or job.get("start_time") or job.get("reporting_time")
    if not raw_time:
        return event_date < (now or datetime.now(IST)).astimezone(IST).date()
    try:
        event_time = raw_time if isinstance(raw_time, time) else time.fromisoformat(str(raw_time))
    except (TypeError, ValueError):
        return event_date < (now or datetime.now(IST)).astimezone(IST).date()

    end_at = datetime.combine(event_date, event_time, tzinfo=IST)
    start_raw = job.get("start_time")
    if job.get("end_time") and start_raw:
        try:
            start_time = start_raw if isinstance(start_raw, time) else time.fromisoformat(str(start_raw))
            if event_time <= start_time:
                from datetime import timedelta
                end_at += timedelta(days=1)
        except (TypeError, ValueError):
            pass
    current = now or datetime.now(IST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=IST)
    else:
        current = current.astimezone(IST)
    return end_at < current

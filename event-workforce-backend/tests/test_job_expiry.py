from datetime import datetime
from zoneinfo import ZoneInfo

import importlib.util
from pathlib import Path

_module_path = Path(__file__).parents[1] / "app" / "jobs" / "expiry.py"
_spec = importlib.util.spec_from_file_location("gigscart_job_expiry", _module_path)
_expiry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_expiry)
job_is_expired = _expiry.job_is_expired

IST = ZoneInfo("Asia/Kolkata")


def test_same_day_job_is_expired_after_end_time():
    job = {
        "job_date": "2026-11-22",
        "start_time": "08:00:00",
        "end_time": "17:00:00",
        "status": "open",
    }
    assert job_is_expired(job, datetime(2026, 11, 22, 18, 0, tzinfo=IST))


def test_overnight_job_is_not_expired_before_next_day_end():
    job = {
        "job_date": "2026-11-22",
        "start_time": "22:00:00",
        "end_time": "02:00:00",
        "status": "open",
    }
    assert not job_is_expired(job, datetime(2026, 11, 23, 1, 0, tzinfo=IST))
    assert job_is_expired(job, datetime(2026, 11, 23, 3, 0, tzinfo=IST))


def test_expired_status_is_always_history():
    assert job_is_expired({"job_date": "2026-11-30", "status": "expired"},
                          datetime(2026, 11, 22, 8, 0, tzinfo=IST))


def test_missing_start_and_end_time_falls_back_to_reporting_time():
    job = {"job_date": "2026-11-22", "reporting_time": "08:00:00", "status": "open"}
    assert job_is_expired(job, datetime(2026, 11, 22, 9, 0, tzinfo=IST))

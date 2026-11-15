from datetime import timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from pydantic import ValidationError

SCHEMA_PATH = Path(__file__).parents[1] / "app" / "jobs" / "schemas.py"
SPEC = spec_from_file_location("gigscart_jobs_schemas", SCHEMA_PATH)
SCHEMAS = module_from_spec(SPEC)
SPEC.loader.exec_module(SCHEMAS)
JobCreate = SCHEMAS.JobCreate
today_ist = SCHEMAS.today_ist


def valid_payload(**overrides):
    payload = {
        "title": "Event Coordinator",
        "category_id": 1,
        "job_date": (today_ist() + timedelta(days=1)).isoformat(),
        "reporting_time": "08:00:00",
        "start_time": "09:00:00",
        "workers_required": 8,
        "salary_per_worker": 500,
        "payment_type": "spot_pay",
        "state": "Tamil Nadu",
        "district": "Chennai",
        "area": "T Nagar",
        "venue_name": "Convention Hall",
        "address": "10 Example Road, Chennai",
    }
    payload.update(overrides)
    return payload


def test_gender_counts_must_sum_to_total_workers():
    job = JobCreate(**valid_payload(male_required=3, female_required=5, trans_required=0))
    assert job.workers_required == 8


def test_gender_count_mismatch_is_rejected():
    with pytest.raises(ValidationError):
        JobCreate(**valid_payload(male_required=3, female_required=4, trans_required=0))


def test_partial_gender_allocation_is_rejected():
    with pytest.raises(ValidationError):
        JobCreate(**valid_payload(male_required=3, female_required=5))


def test_legacy_job_payload_without_gender_counts_remains_valid():
    job = JobCreate(**valid_payload())
    assert job.male_required is None
    assert job.female_required is None
    assert job.trans_required is None

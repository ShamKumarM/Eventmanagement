from app.recommendations.matching import build_top_picks


def _job(**overrides):
    row = {
        "id": "job-1", "title": "Event Coordinator",
        "district": "Tiruvallur", "area": "Avadi",
        "workers_required": 8,
        "male_required": 3, "female_required": 5, "trans_required": 0,
    }
    row.update(overrides)
    return row


def test_top_picks_requires_exact_district_area_title_skill_and_gender():
    jobs = [
        _job(),
        _job(id="wrong-district", district="Chennai"),
        _job(id="wrong-area", area="Ambattur"),
        _job(id="wrong-title", title="Floor Manager"),
        _job(id="no-female-slots", female_required=0),
    ]
    result = build_top_picks(
        jobs, ["Event Coordinator"], "Tiruvallur", "Avadi", "female"
    )
    assert [row["id"] for row in result] == ["job-1"]


def test_top_picks_exact_comparison_ignores_case_and_extra_spaces():
    result = build_top_picks(
        [_job(district=" TIRUVALLUR ", area=" avadi ")],
        ["  event   coordinator "], "Tiruvallur", "Avadi", "female",
    )
    assert len(result) == 1


def test_top_picks_requires_remaining_gender_allocation():
    result = build_top_picks(
        [_job()], ["Event Coordinator"], "Tiruvallur", "Avadi", "female",
        selected_total_by_job={"job-1": 5},
        selected_gender_by_job={"job-1": {"female": 5}},
    )
    assert result == []


def test_legacy_jobs_remain_open_to_all_genders_if_total_capacity_remains():
    result = build_top_picks(
        [_job(male_required=None, female_required=None, trans_required=None)],
        ["Event Coordinator"], "Tiruvallur", "Avadi", "trans",
    )
    assert len(result) == 1


def test_top_picks_is_empty_when_profile_matching_data_is_missing():
    assert build_top_picks([_job()], ["Event Coordinator"], None, "Avadi", "female") == []
    assert build_top_picks([_job()], [], "Tiruvallur", "Avadi", "female") == []
    assert build_top_picks([_job()], ["Event Coordinator"], "Tiruvallur", "Avadi", None) == []

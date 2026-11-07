from app.recommendations.geo import (
    RADIUS_KM, haversine_km, job_point, rank_nearby, resolve_area,
)

GANDHIPURAM = resolve_area("Gandhipuram")


def test_area_matching_ignores_case_spaces_punctuation():
    assert resolve_area("R.S. Puram") == resolve_area("rs puram")
    assert resolve_area("  GANDHIPURAM ") == GANDHIPURAM


def test_unknown_or_empty_area():
    assert resolve_area("Atlantis") is None
    assert resolve_area("") is None
    assert resolve_area(None) is None


def test_haversine():
    assert haversine_km(11.0, 77.0, 11.0, 77.0) == 0
    d = haversine_km(*GANDHIPURAM, *resolve_area("Singanallur"))
    assert 3 < d < 10


def test_job_point_prefers_own_coordinates_then_area():
    assert job_point({"latitude": 11.1, "longitude": 77.1, "area": "Sulur"}) == (11.1, 77.1)
    assert job_point({"latitude": None, "longitude": None, "area": "Sulur"}) == resolve_area("Sulur")
    assert job_point({"area": "Atlantis"}) is None


def test_rank_nearby_filters_sorts_and_strips_coordinates():
    jobs = [
        {"id": "far", "area": "x", "latitude": 10.6609, "longitude": 77.0048, "job_date": "2026-11-20"},  # Pollachi ~40 km
        {"id": "mid", "area": "Singanallur", "job_date": "2026-11-12"},
        {"id": "near", "area": "Gandhipuram", "job_date": "2026-11-15"},
        {"id": "nowhere", "area": "Atlantis", "job_date": "2026-11-10"},
    ]
    out = rank_nearby(jobs, GANDHIPURAM, RADIUS_KM)
    assert [j["id"] for j in out] == ["near", "mid"]
    assert out[0]["distance_km"] <= out[1]["distance_km"] <= RADIUS_KM
    assert all("latitude" not in j for j in out)
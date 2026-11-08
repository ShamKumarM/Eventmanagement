# AbiHub backend fixes — 8 Nov 2026

## Changes
- `GET /recommendations/home` now accepts optional `city`, `area`, `skill`, and `sort_by` query parameters.
- `sort_by` accepts `date`, `recent`, or `pay`.
- Profile avatar uploads normalize supported image formats to a square 900×900 JPEG for circular display.
- Added optional HEIC/HEIF and AVIF decoder packages (`pillow-heif`, `pillow-avif-plugin`).

## Install/update
Run inside the backend virtual environment:

```powershell
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

## Recommendation filter examples
- `/recommendations/home?city=Coimbatore`
- `/recommendations/home?skill=Catering`
- `/recommendations/home?area=Kalapatti&sort_by=recent`
- `/recommendations/home?city=Coimbatore&area=Peelamedu&skill=Security&sort_by=pay`

The endpoint still requires an authenticated worker session.

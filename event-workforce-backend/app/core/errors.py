"""Consistent, plain-language request validation errors for every API module."""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


FIELD_LABELS = {
    "full_name": "Full name",
    "email": "Email address",
    "password": "Password",
    "new_password": "New password",
    "phone": "Mobile number",
    "role": "Account type",
    "organisation_name": "Business / organisation name",
    "title": "Job title",
    "category_id": "Job category",
    "job_id": "Job",
    "application_id": "Application",
    "submission_id": "Verification request",
    "document_id": "Document",
    "status": "Status",
    "payment_type": "Payment method",
    "category_other": "Other job category",
    "description": "Description",
    "job_date": "Event date",
    "reporting_time": "Reporting time",
    "start_time": "Start time",
    "end_time": "End time",
    "workers_required": "Number of workers",
    "salary_per_worker": "Pay per worker",
    "payment_type": "Payment method",
    "payment_days": "Payment days",
    "payment_note": "Payment details",
    "state": "State",
    "district": "District",
    "area": "Area / locality",
    "venue_name": "Venue name",
    "address": "Full address",
    "maps_url": "Map link",
    "food_provided": "Food arrangement",
    "transport_provided": "Transport arrangement",
    "dress_code": "Dress code",
    "preferred_state": "Preferred state",
    "preferred_district": "Preferred district",
    "preferred_area": "Preferred work area",
    "preferred_radius_km": "Travel distance",
    "experience_level": "Experience level",
    "skill_ids": "Skills",
    "cover_note": "Application note",
    "document_type": "Document type",
    "file": "Document file",
    "decision": "Review decision",
    "notes": "Review notes",
    "note": "Review note",
    "confirm_information_accurate": "Information confirmation",
    "website_url": "Website address",
    "business_address": "Business address",
    "contact_person": "Contact person",
    "business_type": "Business type",
    "business_area": "Business area",
    "years_in_business": "Years in business",
}

FIELD_EXAMPLES = {
    "full_name": "Example: Sham Kumar",
    "phone": "Enter a valid phone number with 7 to 15 digits. Example: 9876543210",
    "email": "Example: name@example.com",
    "password": "Use at least 8 characters, including uppercase, lowercase, a number and a symbol.",
    "job_date": "Choose today or a future date.",
    "reporting_time": "Example: 08:30 AM",
    "start_time": "Example: 09:00 AM",
    "end_time": "Example: 05:00 PM",
    "category_id": "Choose a work category from the list.",
    "payment_type": "Choose how and when workers will be paid.",
    "workers_required": "Enter a whole number from 1 to 1000. Example: 12",
    "salary_per_worker": "Enter the amount one worker will receive. Example: 800",
    "state": "Choose a state from the dropdown list.",
    "district": "Choose a district after selecting the state.",
    "area": "Choose an area after selecting the district.",
    "preferred_state": "Choose your preferred state from the list.",
    "preferred_district": "Choose a district after selecting your preferred state.",
    "preferred_area": "Choose a locality after selecting your preferred district.",
    "experience_level": "Choose Beginner, Less than 1 year, 1-2 years, 3-5 years, or 5+ years.",
    "venue_name": "Example: CODISSIA Trade Fair Complex",
    "address": "Enter the building / street, area, landmark and PIN code.",
    "website_url": "Example: https://www.example.com",
    "document_type": "Choose the type that best matches the uploaded document.",
    "file": "Upload a PDF or JPEG file up to 5 MB.",
    "skill_ids": "Choose the work skills you want to show on your profile. You may leave this list empty.",
    "decision": "Choose one of the decisions shown on the review screen.",
}

def _field_name(location: tuple) -> str:
    parts = [str(part) for part in location if part not in {"body", "query", "path", "header"}]
    return parts[-1] if parts else "request"


def _friendly_message(error: dict, field: str) -> str:
    error_type = error.get("type", "")
    original = error.get("msg", "")
    if error_type == "missing":
        return "Please provide this information."
    if error_type == "extra_forbidden":
        return "This information is not needed here. Remove this field and try again."
    if error_type in {"string_too_short", "too_short"}:
        return "This entry is too short. Please add a little more detail."
    if error_type in {"string_too_long", "too_long"}:
        return "This entry is too long. Please shorten it and try again."
    if error_type in {"int_parsing", "float_parsing", "number_parsing"}:
        return "Enter a number using digits only."
    if error_type in {"int_type", "float_type"}:
        return "Enter a valid number."
    if error_type in {"greater_than", "greater_than_equal", "less_than", "less_than_equal"}:
        return "This number is outside the allowed range. Check the guidance and try again."
    if error_type in {"date_from_datetime_parsing", "date_parsing"}:
        return "Enter a valid date. Example: 2026-12-25."
    if error_type in {"time_parsing"}:
        return "Enter a valid time. Example: 09:30."
    if error_type in {"enum", "literal_error"}:
        return "Choose one of the available options."
    if error_type in {"value_error", "assertion_error"}:
        # Pydantic custom validators already provide useful messages.
        clean = original.removeprefix("Value error, ").removeprefix("Assertion failed, ")
        return clean[:240]
    return "Please check this information and try again."


async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = _field_name(tuple(error.get("loc", ())))
        label = FIELD_LABELS.get(field, field.replace("_", " ").capitalize())
        item = {
            "field": field,
            "label": label,
            "message": _friendly_message(error, field),
        }
        example = FIELD_EXAMPLES.get(field)
        if example:
            item["example"] = example
        errors.append(item)

    return JSONResponse(
        status_code=422,
        content={
            "message": "Some information needs your attention. Please correct the fields below and try again.",
            "errors": errors,
        },
    )

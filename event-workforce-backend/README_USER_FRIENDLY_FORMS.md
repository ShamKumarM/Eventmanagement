# User-friendly forms and validation

## Job creation location flow

The employer app should show these fields in order:

1. **State** — dropdown loaded from `GET /locations/states`.
2. **District** — dropdown loaded from `GET /locations/districts?state_id=<selected-state-id>`.
3. **Area / locality** — dropdown loaded from `GET /locations/areas?district_id=<selected-district-id>`.
4. **Venue name** — text input, e.g. `CODISSIA Trade Fair Complex`.
5. **Full address** — text input. Ask for building/street, landmark and PIN code.

When State changes, clear the selected District and Area. When District changes, clear the selected Area. Do not show latitude or longitude inputs. The backend still retains the old coordinate columns for future geocoding/distance features, but they are not accepted in job create/update payloads.

The current seed data in `003_job_location_dropdowns.sql` is intentionally an initial Coimbatore rollout: Tamil Nadu > Coimbatore, with common Coimbatore localities. Add more states, districts and areas to the lookup tables as service coverage expands. Do not present an empty dropdown as an invalid user entry; show a helpful “Location not available yet” message and ask the admin to add the locality.

## Job create request example

```json
{
  "title": "Event Service Staff",
  "category_id": 1,
  "description": "Assist with guest service during the event.",
  "job_date": "2026-12-20",
  "reporting_time": "08:30:00",
  "start_time": "09:00:00",
  "end_time": "17:00:00",
  "workers_required": 12,
  "salary_per_worker": 800,
  "payment_type": "spot_pay",
  "state": "Tamil Nadu",
  "district": "Coimbatore",
  "area": "Peelamedu",
  "venue_name": "CODISSIA Trade Fair Complex",
  "address": "GATE 4, Avinashi Road, Peelamedu, Coimbatore - 641014",
  "food_provided": true,
  "transport_provided": false,
  "dress_code": "Black trousers and white shirt"
}
```

## Plain-language validation response

All FastAPI request validation errors now use a shared response format:

```json
{
  "message": "Some information needs your attention. Please correct the fields below and try again.",
  "errors": [
    {
      "field": "workers_required",
      "label": "Number of workers",
      "message": "This number is outside the allowed range. Check the guidance and try again.",
      "example": "Enter a whole number from 1 to 1000. Example: 12"
    }
  ]
}
```

The frontend should display each error beside the matching field using `field`, show `message`, and optionally show `example`. Do not show raw Pydantic error codes to end users.

## Field guidance for the frontend

- Full name: “Enter your first and last name.” Example: Sham Kumar.
- Mobile number: “Enter a reachable mobile number.” Example: 9876543210.
- Email: “Use an email address you can access.” Example: name@example.com.
- Password: “At least 8 characters, with uppercase, lowercase, number and symbol.”
- Job title: “Name the role workers will perform.” Example: Event Service Staff.
- Job category: “Choose the closest matching work category.”
- Event date: “Choose the date workers should report.”
- Reporting time: “When workers must arrive at the venue.”
- Start / end time: “When the work begins and finishes.”
- Number of workers: “How many people you need.” Example: 12.
- Pay per worker: “Amount each selected worker will receive.” Example: ₹800.
- State / District / Area: select from the previous dropdown; do not type IDs.
- Venue name: “Name of the event venue.” Example: CODISSIA Trade Fair Complex.
- Full address: “Building or street, landmark, locality and PIN code.”
- Employer document: “Upload a PDF or JPEG up to 5 MB.”
- Review decision: “Choose Approve or Reject from the available actions.”

## Deployment order

1. Run `003_job_location_dropdowns.sql` in Supabase SQL Editor.
2. Replace the local backend files with this updated backend.
3. Restart FastAPI.
4. Test the three location dropdown endpoints using a logged-in account.
5. Test job creation with the example payload (change date to a future date).
6. Update Flutter forms to consume the `errors` array and show inline messages.

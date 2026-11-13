# Jobs module

The jobs router is registered by `app.main` and uses the Supabase service-role
client on the backend. Configure `SUPABASE_URL`, `SUPABASE_KEY`, and
`SUPABASE_SERVICE_KEY` in the backend `.env`; never put the service-role key in
the Flutter app.

Apply the numbered jobs, location, and category SQL setup files to the same
Supabase project used by the API. See `API_MODULE_CONNECTION_MAP.md` for the
current routes and `README_USER_FRIENDLY_FORMS.md` for the job-create payload.

Run locally from this directory with `python -m uvicorn app.main:app --reload`.

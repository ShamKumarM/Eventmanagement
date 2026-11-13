# Event Workforce Platform

This checkout contains the FastAPI backend for the event workforce platform, backed by Supabase Auth, Postgres, and Storage. The Flutter app source is not included in this checkout.

## Run the backend locally

1. Install dependencies from `event-workforce-backend/requirements.txt`.
2. Copy `event-workforce-backend/.env.example` to `event-workforce-backend/.env` and set the Supabase URL, public key, service-role key, and recovery redirect URL. Keep `.env` private.
3. Start the API from the backend directory:

   ```powershell
   cd event-workforce-backend
   python -m uvicorn app.main:app --reload
   ```

4. Open `http://127.0.0.1:8000/docs` or check `http://127.0.0.1:8000/health`.

## API and database notes

- API routes and integration notes: [API_MODULE_CONNECTION_MAP.md](event-workforce-backend/API_MODULE_CONNECTION_MAP.md)
- Worker connections and chat: [README_SOCIAL.md](event-workforce-backend/README_SOCIAL.md)
- Employer follows and contact sharing: [README_EMPLOYER_FOLLOW.md](event-workforce-backend/README_EMPLOYER_FOLLOW.md)
- SQL setup files are applied to Supabase manually; deploying Python does not apply migrations automatically.

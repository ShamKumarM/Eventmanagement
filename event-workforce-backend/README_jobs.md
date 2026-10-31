# Jobs module – hookup

1. Copy `jobs/` next to `main.py`; run `sql/001_jobs_schema.sql` in Supabase.
2. Add to `.env`:  SUPABASE_SERVICE_KEY=<service_role key>   (server only!)
3. In `main.py` add:

       from jobs import jobs_router
       app.include_router(jobs_router)

4. `uvicorn main:app --reload`, then open /docs.

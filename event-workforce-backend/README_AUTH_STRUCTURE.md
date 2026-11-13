# Backend module structure

Authentication now follows the same feature-module layout as Jobs:

```text
app/
  auth/
    __init__.py
    router.py   # /auth endpoints
    schemas.py  # Pydantic request models
    deps.py     # shared bearer-token validation
  jobs/
    __init__.py
    router.py
    schemas.py
    deps.py     # imports shared get_current_user
    db.py
  core/
    config.py
  services/
    supabase_client.py
  main.py
```

The existing authentication endpoint paths and request schemas are preserved.
`main.py` imports the authentication router from `app.auth.router`. Jobs imports
`get_current_user` from `app.auth.deps`, so token validation is defined once.

## Run locally

1. Ensure your local `.env` contains the cloud Supabase URL and keys expected by
   `app/core/config.py` and `app/jobs/db.py`. Never commit `.env` or share secret keys.
2. Install project dependencies from `requirements.txt`.
3. Start the API with `uvicorn app.main:app --reload`.
4. Open `http://127.0.0.1:8000/docs` and test the existing routes.

Jobs routes enforce the selected employer role through their shared dependency.

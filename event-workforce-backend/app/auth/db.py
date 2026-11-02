"""Privileged database client for trusted backend-only operations.

Never expose SUPABASE_SERVICE_KEY to clients or use this client to authenticate
incoming users. Validate user access tokens with app.auth.deps first.
"""
import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_url = os.getenv("SUPABASE_URL", "").strip()
_service_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

if not _url or not _service_key:
    raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")

admin_db: Client = create_client(_url, _service_key)

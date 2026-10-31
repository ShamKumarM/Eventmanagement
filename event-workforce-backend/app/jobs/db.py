"""Dedicated Supabase client for data access (service-role key).

Kept separate from the auth client in main.py: supabase-py stores the
signed-in user's session on the client object after sign_in_with_password(),
which can silently change the credentials used for later table queries.
Never expose the service-role key to the mobile app.
"""
import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_url = os.getenv("SUPABASE_URL")
_key = os.getenv("SUPABASE_SERVICE_KEY")

if not _url or not _key:
    raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")

db: Client = create_client(_url, _key)

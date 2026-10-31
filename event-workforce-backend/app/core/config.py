
import os

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

RECOVERY_REDIRECT_URL = os.getenv(
    "RECOVERY_REDIRECT_URL",
    "http://127.0.0.1:8000/auth/recovery/callback",
).strip()

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_KEY must be configured in .env"
    )


from supabase import create_client

from app.core.config import SUPABASE_URL, SUPABASE_KEY


def create_supabase_client():
    """Create an independent Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# Shared client for ordinary auth operations.
supabase = create_supabase_client()

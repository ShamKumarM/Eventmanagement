"""Provision or replace the single administrator out-of-band.

Usage (PowerShell):
  $env:ADMIN_USER_ID = "<existing Supabase auth user UUID>"
  python -m scripts.bootstrap_admin

This script requires SUPABASE_URL and SUPABASE_SERVICE_KEY in .env.
It deliberately does not expose admin registration through the public API.
Deactivate the current admin_access row before provisioning a replacement.
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL", "").strip()
key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
user_id = os.getenv("ADMIN_USER_ID", "").strip()

if not url or not key or not user_id:
    raise SystemExit("Set SUPABASE_URL, SUPABASE_SERVICE_KEY and ADMIN_USER_ID.")

client = create_client(url, key)

active = (
    client.table("admin_access")
    .select("user_id")
    .eq("is_active", True)
    .limit(1)
    .execute()
)
if active.data:
    raise SystemExit(
        "An active admin already exists. Deactivate that admin_access row first."
    )

profile_result = (
    client.table("profiles")
    .select("id, role, role_selected")
    .eq("id", user_id)
    .limit(1)
    .execute()
)
if not profile_result.data:
    raise SystemExit("ADMIN_USER_ID must belong to an existing registered user.")

original = profile_result.data[0]
original_role = original.get("role")
original_role_selected = original.get("role_selected")

# Promote only the selected existing account; never create a user here.
client.table("profiles").update(
    {"role": "admin", "role_selected": True}
).eq("id", user_id).execute()

try:
    existing_access = (
        client.table("admin_access")
        .select("user_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if existing_access.data:
        client.table("admin_access").update(
            {"is_active": True, "deactivated_at": None}
        ).eq("user_id", user_id).execute()
    else:
        client.table("admin_access").insert(
            {"user_id": user_id, "is_active": True}
        ).execute()
except Exception:
    # Restore the exact prior role; do not assume it was a worker.
    client.table("profiles").update(
        {"role": original_role, "role_selected": original_role_selected}
    ).eq("id", user_id).execute()
    raise

print(f"Administrator provisioned successfully: {user_id}")

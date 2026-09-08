"""
Supabase client(s).

We keep two clients:
- `supabase_admin`: uses the SERVICE ROLE key. Bypasses Row Level Security.
  Only ever used server-side, and only after we have already verified which
  user is making the request (see app/dependencies.py). Every query built
  from this client MUST be explicitly filtered by the verified user id.
- Row Level Security is still enabled on every table as defense in depth,
  in case a future code path forgets to filter.
"""
from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_supabase_admin() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not configured. "
            "Set them in backend/.env"
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)

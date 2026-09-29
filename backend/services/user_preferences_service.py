"""
user_preferences_service.py

Fetches (and lazily creates, with sensible defaults) a user's AI writing
preferences. Used by reply_generator.py, and later by Module 7's settings
UI.
"""
from __future__ import annotations

from database.supabase_client import get_supabase_admin
from services.db_utils import get_or_create_row

DEFAULT_PREFERENCES = {
    "tone": "Professional",
    "language": "en",
    "signature": None,
    "custom_instructions": None,
    "auto_reply_enabled": False,
    "reply_length": "medium",
}


def get_or_create_preferences(user_id: str) -> dict:
    return get_or_create_row(get_supabase_admin(), "user_ai_preferences", "user_id", user_id, DEFAULT_PREFERENCES)


def update_preferences(user_id: str, updates: dict) -> dict:
    get_or_create_preferences(user_id)  # ensure a row exists first
    if updates:
        get_supabase_admin().table("user_ai_preferences").update(updates).eq("user_id", user_id).execute()
    return get_or_create_preferences(user_id)

"""
db_utils.py

Shared helper for the "one row per user, create with defaults on first
access" pattern used by profiles, user_ai_preferences, and
automation_settings.

SECURITY/CORRECTNESS NOTE (Module 8 audit finding): the naive
check-then-insert pattern (select, see nothing, insert) has a race
condition — two concurrent first-requests from the same user (e.g. two
browser tabs loading simultaneously) can both see no existing row and
both attempt to insert, and the loser hits the table's unique constraint
on the user id column. Previously this surfaced as an unhandled 500. This
helper catches that specific failure and re-fetches the row the winner
just inserted, instead of raising.
"""
from __future__ import annotations

import logging

from database.supabase_client import get_supabase_admin

logger = logging.getLogger("ai_mail_assistant.db_utils")


def get_or_create_row(db, table: str, id_column: str, id_value: str, defaults: dict) -> dict:
    """
    `db` is the caller's own already-resolved Supabase client (i.e. call
    this as `get_or_create_row(get_supabase_admin(), ...)` using the
    caller module's own `get_supabase_admin` import) rather than fetching
    a client internally — this keeps the helper's DB access swappable via
    each service module's own monkeypatchable reference, which the test
    suite relies on.
    """
    existing = db.table(table).select("*").eq(id_column, id_value).limit(1).execute()
    if existing.data:
        return existing.data[0]

    payload = {id_column: id_value, **defaults}
    try:
        result = db.table(table).insert(payload).execute()
        return result.data[0] if result.data else payload
    except Exception as exc:
        if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
            # Lost the race to a concurrent request — fetch what it inserted
            # rather than surfacing an error for what is, from the caller's
            # perspective, a completely normal "row already exists" outcome.
            existing = db.table(table).select("*").eq(id_column, id_value).limit(1).execute()
            if existing.data:
                return existing.data[0]
        logger.exception("get_or_create_row failed for table=%s", table)
        raise

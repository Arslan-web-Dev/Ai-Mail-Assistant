"""
processing_log.py

Single shared implementation of "write a row to email_processing_logs,
never let a logging failure break the caller." Previously duplicated
verbatim across ai_analyzer.py, reply_generator.py, email_sync_service.py,
draft_service.py, and automation_service.py — consolidated here as part
of the Module 8 audit (duplicated code).
"""
from __future__ import annotations

import logging

from database.supabase_client import get_supabase_admin

logger = logging.getLogger("ai_mail_assistant.processing_log")


def log_event(user_id: str, email_id: str | None, stage: str, status: str, message: str = "") -> None:
    try:
        get_supabase_admin().table("email_processing_logs").insert(
            {
                "user_id": user_id,
                "email_id": email_id,
                "stage": stage,
                "status": status,
                "message": message[:2000],  # never log secrets/tokens; message is always our own text
            }
        ).execute()
    except Exception:
        logger.exception("Failed to write processing log (non-fatal): stage=%s", stage)

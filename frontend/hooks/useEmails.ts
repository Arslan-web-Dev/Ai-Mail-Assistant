"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, emailsApi } from "@/services/api";
import type { EmailFilter, EmailSummary } from "@/types";

export function useEmails(search: string, filter: EmailFilter) {
  const [items, setItems] = useState<EmailSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await emailsApi.list({ search: search || undefined, filter, limit: 25 });
      setItems(page.items as EmailSummary[]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load emails");
    } finally {
      setLoading(false);
    }
  }, [search, filter]);

  useEffect(() => {
    load();
  }, [load]);

  const loadMore = useCallback(async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await emailsApi.list({ search: search || undefined, filter, cursor: nextCursor, limit: 25 });
      setItems((prev) => [...prev, ...(page.items as EmailSummary[])]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load more emails");
    } finally {
      setLoadingMore(false);
    }
  }, [nextCursor, loadingMore, search, filter]);

  return { items, loading, loadingMore, error, hasMore: !!nextCursor, loadMore, refresh: load };
}

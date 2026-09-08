"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, draftsApi } from "@/services/api";
import type { Draft } from "@/types";

export function useDrafts(status: string) {
  const [items, setItems] = useState<Draft[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await draftsApi.list({ status: status === "all" ? undefined : status, limit: 20 });
      setItems(page.items as Draft[]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load drafts");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  const loadMore = useCallback(async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await draftsApi.list({
        status: status === "all" ? undefined : status,
        cursor: nextCursor,
        limit: 20,
      });
      setItems((prev) => [...prev, ...(page.items as Draft[])]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load more drafts");
    } finally {
      setLoadingMore(false);
    }
  }, [nextCursor, loadingMore, status]);

  const replaceItem = useCallback((updated: Draft) => {
    setItems((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
  }, []);

  return { items, loading, loadingMore, error, hasMore: !!nextCursor, loadMore, refresh: load, replaceItem };
}

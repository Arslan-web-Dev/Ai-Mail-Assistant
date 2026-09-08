"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, gmailApi } from "@/services/api";
import type { GmailStatus } from "@/types";

export function useGmailStatus() {
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await gmailApi.getStatus();
      setStatus(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load Gmail status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { status, loading, error, refresh };
}

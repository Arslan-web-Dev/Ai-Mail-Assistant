"use client";

import { useState } from "react";

import { ApiError, gmailApi } from "@/services/api";
import type { GmailStatus } from "@/types";

interface Props {
  status: GmailStatus | null;
  onChange: () => void | Promise<void>;
}

export function GmailConnectButton({ status, onChange }: Props) {
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleConnect = async () => {
    setBusy(true);
    setLocalError(null);
    try {
      const { authorization_url } = await gmailApi.getAuthorizationUrl();
      window.location.href = authorization_url;
    } catch (err) {
      setLocalError(err instanceof ApiError ? err.message : "Could not start Gmail connection");
      setBusy(false);
    }
  };

  const handleDisconnect = async () => {
    setBusy(true);
    setLocalError(null);
    try {
      await gmailApi.disconnect();
      await onChange();
    } catch (err) {
      setLocalError(err instanceof ApiError ? err.message : "Could not disconnect Gmail");
    } finally {
      setBusy(false);
    }
  };

  const isConnected = status?.status === "connected";

  return (
    <div className="space-y-3">
      {isConnected ? (
        <button
          onClick={handleDisconnect}
          disabled={busy}
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 transition hover:bg-red-100 disabled:opacity-50"
        >
          {busy ? "Disconnecting…" : "Disconnect Gmail"}
        </button>
      ) : (
        <button
          onClick={handleConnect}
          disabled={busy}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:opacity-50"
        >
          {busy ? "Connecting…" : "Connect Gmail"}
        </button>
      )}
      {localError && <p className="text-sm text-red-600">{localError}</p>}
    </div>
  );
}

"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ProtectedShell } from "@/components/ProtectedShell";
import { GmailConnectButton } from "@/components/GmailConnectButton";
import { GmailStatusBadge } from "@/components/GmailStatusBadge";
import { useGmailStatus } from "@/hooks/useGmailStatus";

const CALLBACK_MESSAGES: Record<string, { tone: "error" | "info"; text: string }> = {
  denied: { tone: "info", text: "Gmail connection was cancelled." },
  invalid_request: { tone: "error", text: "Gmail redirected back with an invalid request." },
  invalid_state: {
    tone: "error",
    text: "That connection request expired or was invalid. Please try again.",
  },
  error: { tone: "error", text: "Something went wrong connecting Gmail. Please try again." },
  connected: { tone: "info", text: "Gmail connected successfully." },
};

export default function GmailSettingsPage() {
  return (
    <Suspense fallback={null}>
      <GmailSettingsContent />
    </Suspense>
  );
}

function GmailSettingsContent() {
  const { status, loading, error, refresh } = useGmailStatus();
  const searchParams = useSearchParams();
  const [callbackNotice, setCallbackNotice] = useState<
    { tone: "error" | "info"; text: string } | null
  >(null);

  useEffect(() => {
    const gmailStatus = searchParams.get("gmail_status");
    if (gmailStatus && CALLBACK_MESSAGES[gmailStatus]) {
      setCallbackNotice(CALLBACK_MESSAGES[gmailStatus]);
      // Clean the query string so a refresh doesn't re-show the notice.
      window.history.replaceState({}, "", "/settings/gmail");
      refresh();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  return (
    <ProtectedShell>
      <h1 className="text-2xl font-semibold text-slate-900">Gmail connection</h1>
      <p className="mt-1 text-sm text-slate-600">
        AI Mail Assistant needs access to Gmail to read incoming email and send
        approved replies on your behalf.
      </p>

      {callbackNotice && (
        <div
          className={`mt-4 rounded-lg border px-4 py-3 text-sm ${
            callbackNotice.tone === "error"
              ? "border-red-200 bg-red-50 text-red-700"
              : "border-blue-200 bg-blue-50 text-blue-700"
          }`}
        >
          {callbackNotice.text}
        </div>
      )}

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <h2 className="font-medium text-slate-900">Status</h2>
          {loading ? (
            <span className="text-sm text-slate-400">Checking…</span>
          ) : status ? (
            <GmailStatusBadge status={status.status} />
          ) : null}
        </div>

        {status?.gmail_email && (
          <p className="mt-2 text-sm text-slate-600">
            Connected as <span className="font-medium">{status.gmail_email}</span>
          </p>
        )}

        {status?.status === "error" && status.last_error && (
          <p className="mt-2 text-sm text-red-600">{status.last_error}</p>
        )}

        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

        <div className="mt-5">
          <GmailConnectButton status={status} onChange={refresh} />
        </div>
      </div>

      <div className="mt-4 text-xs text-slate-500">
        We request the minimum Gmail permissions needed: read your mail,
        modify labels, and send messages. We never access your password, and
        you can disconnect at any time.
      </div>
    </ProtectedShell>
  );
}

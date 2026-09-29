"use client";

import { useState } from "react";

import { ApiError, draftsApi } from "@/services/api";
import type { Draft } from "@/types";

const STATUS_STYLES: Record<string, string> = {
  ready: "bg-blue-100 text-blue-800",
  edited: "bg-purple-100 text-purple-800",
  approved: "bg-green-100 text-green-800",
  sent: "bg-green-100 text-green-800",
  rejected: "bg-slate-200 text-slate-700",
  failed: "bg-red-100 text-red-700",
  generating: "bg-amber-100 text-amber-800",
};

export function DraftPanel({ draft, onChange }: { draft: Draft; onChange: (draft: Draft) => void }) {
  const [content, setContent] = useState(draft.edited_content ?? draft.generated_content);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const isFinal = draft.status === "sent" || draft.status === "rejected";

  const run = async (action: string, fn: () => Promise<Draft>) => {
    setBusy(action);
    setError(null);
    try {
      const updated = await fn();
      onChange(updated);
      if (action === "save") setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Failed to ${action}`);
    } finally {
      setBusy(null);
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-slate-900">AI draft reply</h3>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[draft.status] || "bg-slate-100 text-slate-700"}`}>
          {draft.status}
        </span>
      </div>

      {draft.requires_review && draft.status !== "sent" && (
        <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
          This draft is flagged for careful review before sending.
        </p>
      )}

      {draft.subject && <p className="mt-3 text-sm font-medium text-slate-700">Subject: {draft.subject}</p>}

      {editing ? (
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={10}
          className="mt-2 w-full rounded-lg border border-slate-300 p-3 text-sm focus:border-brand-500 focus:outline-none"
        />
      ) : (
        <p className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm text-slate-800">{content}</p>
      )}

      {typeof draft.confidence === "number" && (
        <p className="mt-2 text-xs text-slate-500">AI confidence: {Math.round(draft.confidence * 100)}%</p>
      )}

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {!isFinal && (
        <div className="mt-4 flex flex-wrap gap-2">
          {editing ? (
            <>
              <button
                onClick={() => run("save", () => draftsApi.update(draft.id, content, draft.subject ?? undefined))}
                disabled={busy !== null}
                className="rounded-lg bg-slate-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-900 disabled:opacity-50"
              >
                {busy === "save" ? "Saving…" : "Save"}
              </button>
              <button
                onClick={() => setEditing(false)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              onClick={() => setEditing(true)}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Edit
            </button>
          )}

          <button
            onClick={handleCopy}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            {copied ? "Copied!" : "Copy"}
          </button>

          <button
            onClick={() => run("regenerate", () => draftsApi.regenerate(draft.id))}
            disabled={busy !== null}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {busy === "regenerate" ? "Regenerating…" : "Regenerate"}
          </button>

          <button
            onClick={() => run("reject", () => draftsApi.reject(draft.id))}
            disabled={busy !== null}
            className="rounded-lg border border-red-200 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
          >
            {busy === "reject" ? "Rejecting…" : "Reject"}
          </button>

          <button
            onClick={() => run("approve", () => draftsApi.approve(draft.id))}
            disabled={busy !== null}
            className="ml-auto rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {busy === "approve" ? "Sending…" : "Approve & Send"}
          </button>
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";

import { ProtectedShell } from "@/components/ProtectedShell";
import { DraftPanel } from "@/components/DraftPanel";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/StateViews";
import { useDrafts } from "@/hooks/useDrafts";

const STATUS_TABS = [
  { value: "all", label: "All" },
  { value: "ready", label: "Ready" },
  { value: "edited", label: "Edited" },
  { value: "sent", label: "Sent" },
  { value: "rejected", label: "Rejected" },
  { value: "failed", label: "Failed" },
];

export default function DraftsPage() {
  const [status, setStatus] = useState("all");
  const { items, loading, loadingMore, error, hasMore, loadMore, refresh, replaceItem } = useDrafts(status);

  return (
    <ProtectedShell>
      <h1 className="text-2xl font-semibold text-slate-900">Drafts</h1>
      <p className="mt-1 text-sm text-slate-600">Review, edit, and approve AI-generated replies.</p>

      <div className="mt-4 flex flex-wrap gap-2">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatus(tab.value)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
              status === tab.value
                ? "border-brand-500 bg-brand-50 text-brand-700"
                : "border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {loading ? (
          <ListSkeleton />
        ) : error ? (
          <ErrorState message={error} onRetry={refresh} />
        ) : items.length === 0 ? (
          <EmptyState title="No drafts here" description="AI-generated replies awaiting review will show up here." />
        ) : (
          <div className="space-y-3">
            {items.map((draft) => (
              <DraftPanel key={draft.id} draft={draft} onChange={replaceItem} />
            ))}
            {hasMore && (
              <div className="text-center">
                <button
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="text-sm font-medium text-brand-600 hover:underline disabled:opacity-50"
                >
                  {loadingMore ? "Loading…" : "Load more"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </ProtectedShell>
  );
}

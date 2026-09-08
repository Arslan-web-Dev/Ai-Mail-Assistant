"use client";

import { useState } from "react";

import { ProtectedShell } from "@/components/ProtectedShell";
import { EmailListItem } from "@/components/EmailListItem";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/StateViews";
import { useEmails } from "@/hooks/useEmails";
import { useGmailStatus } from "@/hooks/useGmailStatus";
import type { EmailFilter } from "@/types";

const FILTERS: { value: EmailFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "unread", label: "Unread" },
  { value: "needs_reply", label: "Needs Reply" },
  { value: "drafts", label: "Drafts" },
  { value: "sent", label: "Sent" },
  { value: "high_priority", label: "High Priority" },
  { value: "job", label: "Job" },
  { value: "business", label: "Business" },
  { value: "meeting", label: "Meeting" },
  { value: "personal", label: "Personal" },
];

export default function InboxPage() {
  const { status } = useGmailStatus();
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [filter, setFilter] = useState<EmailFilter>("all");
  const { items, loading, loadingMore, error, hasMore, loadMore, refresh } = useEmails(search, filter);

  return (
    <ProtectedShell>
      <h1 className="text-2xl font-semibold text-slate-900">Inbox</h1>

      {status?.status !== "connected" && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          Connect Gmail in Settings to start syncing your inbox.
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setSearch(searchInput);
        }}
        className="mt-4 flex gap-2"
      >
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search subject, sender, or body…"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
        />
        <button
          type="submit"
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Search
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
              filter === f.value
                ? "border-brand-500 bg-brand-50 text-brand-700"
                : "border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
        {loading ? (
          <ListSkeleton />
        ) : error ? (
          <ErrorState message={error} onRetry={refresh} />
        ) : items.length === 0 ? (
          <EmptyState
            title="No emails here"
            description={search || filter !== "all" ? "Try a different search or filter." : "Synced emails will show up here."}
          />
        ) : (
          <>
            <div>
              {items.map((email) => (
                <EmailListItem key={email.id} email={email} />
              ))}
            </div>
            {hasMore && (
              <div className="border-t border-slate-100 p-3 text-center">
                <button
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="text-sm font-medium text-brand-600 hover:underline disabled:opacity-50"
                >
                  {loadingMore ? "Loading…" : "Load more"}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </ProtectedShell>
  );
}

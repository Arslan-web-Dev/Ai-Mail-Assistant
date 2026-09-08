"use client";

import { ProtectedShell } from "@/components/ProtectedShell";
import { EmailListItem } from "@/components/EmailListItem";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/StateViews";
import { useEmails } from "@/hooks/useEmails";

export default function SentPage() {
  const { items, loading, error, hasMore, loadMore, loadingMore, refresh } = useEmails("", "sent");

  return (
    <ProtectedShell>
      <h1 className="text-2xl font-semibold text-slate-900">Sent</h1>
      <p className="mt-1 text-sm text-slate-600">
        Emails you've replied to via AI Mail Assistant.
      </p>

      <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
        {loading ? (
          <ListSkeleton />
        ) : error ? (
          <ErrorState message={error} onRetry={refresh} />
        ) : items.length === 0 ? (
          <EmptyState title="Nothing sent yet" description="Replies you approve will appear here." />
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

import Link from "next/link";

import type { EmailSummary } from "@/types";

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  return sameDay
    ? date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function EmailListItem({ email }: { email: EmailSummary }) {
  return (
    <Link
      href={`/inbox/${email.id}`}
      className="flex items-start gap-3 border-b border-slate-100 px-4 py-3 transition hover:bg-slate-50"
    >
      <span
        className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${
          email.is_read ? "bg-transparent" : "bg-brand-500"
        }`}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <p className={`truncate text-sm ${email.is_read ? "text-slate-600" : "font-semibold text-slate-900"}`}>
            {email.sender}
          </p>
          <span className="flex-shrink-0 text-xs text-slate-400">{formatDate(email.received_at)}</span>
        </div>
        <p className="truncate text-sm text-slate-800">{email.subject || "(no subject)"}</p>
        <p className="truncate text-xs text-slate-500">{email.snippet}</p>
      </div>
      {email.requires_reply && (
        <span className="mt-1 flex-shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
          Needs reply
        </span>
      )}
    </Link>
  );
}

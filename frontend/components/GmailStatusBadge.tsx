import type { GmailConnectionStatus } from "@/types";

const STYLES: Record<GmailConnectionStatus, string> = {
  connected: "bg-green-100 text-green-800 border-green-200",
  disconnected: "bg-slate-100 text-slate-700 border-slate-200",
  connecting: "bg-amber-100 text-amber-800 border-amber-200",
  error: "bg-red-100 text-red-700 border-red-200",
};

const LABELS: Record<GmailConnectionStatus, string> = {
  connected: "Connected",
  disconnected: "Disconnected",
  connecting: "Connecting…",
  error: "Connection Error",
};

export function GmailStatusBadge({ status }: { status: GmailConnectionStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${STYLES[status]}`}
    >
      <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current" />
      {LABELS[status]}
    </span>
  );
}

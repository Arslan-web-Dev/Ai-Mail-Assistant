"use client";

import { useEffect, useState } from "react";

import { ProtectedShell } from "@/components/ProtectedShell";
import { ErrorState } from "@/components/StateViews";
import { ApiError, analyticsApi } from "@/services/api";
import type { AnalyticsRange, AnalyticsSummary } from "@/types";

const RANGE_OPTIONS: { value: AnalyticsRange; label: string }[] = [
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
];

const STAT_ITEMS: { key: keyof AnalyticsSummary; label: string }[] = [
  { key: "total_emails", label: "Total Emails" },
  { key: "emails_processed", label: "Emails Processed" },
  { key: "replies_generated", label: "Replies Generated" },
  { key: "replies_sent", label: "Replies Sent" },
  { key: "auto_replies", label: "Auto Replies" },
  { key: "manual_replies", label: "Manual Replies" },
  { key: "rejected_drafts", label: "Rejected Drafts" },
  { key: "failed_replies", label: "Failed Replies" },
];

function BarRow({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-slate-600">
        <span className="capitalize">{label.replace(/_/g, " ")}</span>
        <span>{value}</span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-slate-100">
        <div className="h-2 rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [range, setRange] = useState<AnalyticsRange>("30d");
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    analyticsApi
      .getSummary(range)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load analytics"))
      .finally(() => setLoading(false));
  };

  useEffect(load, [range]);

  const categoryMax = data ? Math.max(1, ...Object.values(data.category_breakdown)) : 1;
  const automationMax = data ? Math.max(1, ...Object.values(data.automation_activity)) : 1;

  return (
    <ProtectedShell>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Analytics</h1>
        <div className="flex gap-1 rounded-lg border border-slate-200 p-1">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setRange(opt.value)}
              className={`rounded-md px-3 py-1 text-xs font-medium ${
                range === opt.value ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="mt-6 text-sm text-slate-500">Loading…</p>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : data ? (
        <div className="mt-6 space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {STAT_ITEMS.map((item) => (
              <div key={item.key} className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{item.label}</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{data[item.key] as number}</p>
              </div>
            ))}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Avg AI Confidence</p>
              <p className="mt-1 text-2xl font-semibold text-slate-900">
                {data.average_ai_confidence !== null ? `${Math.round(data.average_ai_confidence * 100)}%` : "—"}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Avg Processing Time</p>
              <p className="mt-1 text-2xl font-semibold text-slate-900">
                {data.average_processing_time_seconds !== null
                  ? `${Math.round(data.average_processing_time_seconds)}s`
                  : "—"}
              </p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="font-medium text-slate-900">Email categories</h2>
              {Object.keys(data.category_breakdown).length === 0 ? (
                <p className="mt-3 text-sm text-slate-400">No data yet for this range.</p>
              ) : (
                <div className="mt-3 space-y-3">
                  {Object.entries(data.category_breakdown).map(([cat, count]) => (
                    <BarRow key={cat} label={cat} value={count} max={categoryMax} />
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="font-medium text-slate-900">Automation activity</h2>
              {Object.keys(data.automation_activity).length === 0 ? (
                <p className="mt-3 text-sm text-slate-400">No automation decisions yet for this range.</p>
              ) : (
                <div className="mt-3 space-y-3">
                  {Object.entries(data.automation_activity).map(([decision, count]) => (
                    <BarRow key={decision} label={decision} value={count} max={automationMax} />
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="font-medium text-slate-900">Reply activity</h2>
            {data.reply_activity.length === 0 ? (
              <p className="mt-3 text-sm text-slate-400">No replies sent yet in this range.</p>
            ) : (
              <div className="mt-4 flex items-end gap-1" style={{ height: 120 }}>
                {data.reply_activity.map((point) => {
                  const max = Math.max(1, ...data.reply_activity.map((p) => p.count));
                  const height = Math.max(4, Math.round((point.count / max) * 110));
                  return (
                    <div key={point.date} className="flex flex-1 flex-col items-center gap-1" title={`${point.date}: ${point.count}`}>
                      <div className="w-full rounded-t bg-brand-500" style={{ height }} />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </ProtectedShell>
  );
}

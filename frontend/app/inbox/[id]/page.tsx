"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { ProtectedShell } from "@/components/ProtectedShell";
import { DraftPanel } from "@/components/DraftPanel";
import { ErrorState } from "@/components/StateViews";
import { ApiError, emailsApi } from "@/services/api";
import type { EmailDetail } from "@/types";

const SENSITIVITY_STYLES: Record<string, string> = {
  LOW: "bg-green-100 text-green-800",
  MEDIUM: "bg-amber-100 text-amber-800",
  HIGH: "bg-orange-100 text-orange-800",
  CRITICAL: "bg-red-100 text-red-700",
};

export default function EmailDetailPage() {
  const params = useParams();
  const emailId = params.id as string;

  const [detail, setDetail] = useState<EmailDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    emailsApi
      .getDetail(emailId)
      .then(setDetail)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load email"))
      .finally(() => setLoading(false));
  };

  useEffect(load, [emailId]);

  const handleGenerateReply = async () => {
    setGenerating(true);
    try {
      await emailsApi.generateReply(emailId);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate reply");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <ProtectedShell>
      <Link href="/inbox" className="text-sm text-slate-500 hover:text-slate-800">
        ← Back to inbox
      </Link>

      {loading ? (
        <p className="mt-6 text-sm text-slate-500">Loading…</p>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : detail ? (
        <div className="mt-4 space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h1 className="text-lg font-semibold text-slate-900">{detail.email.subject || "(no subject)"}</h1>
            <p className="mt-1 text-sm text-slate-600">From: {detail.email.sender}</p>
            {detail.email.recipient && <p className="text-sm text-slate-600">To: {detail.email.recipient}</p>}
            <p className="mt-3 whitespace-pre-wrap text-sm text-slate-800">
              {detail.email.body_text || detail.email.snippet}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="font-medium text-slate-900">AI analysis</h2>
            {detail.analysis ? (
              <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                <div>
                  <p className="text-xs text-slate-500">Category</p>
                  <p className="font-medium text-slate-800">{detail.analysis.category}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Priority</p>
                  <p className="font-medium text-slate-800">{detail.analysis.priority}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Sentiment</p>
                  <p className="font-medium text-slate-800">{detail.analysis.sentiment}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Sensitivity</p>
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${SENSITIVITY_STYLES[detail.analysis.sensitivity_level] || ""}`}
                  >
                    {detail.analysis.sensitivity_level}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Confidence</p>
                  <p className="font-medium text-slate-800">{Math.round(detail.analysis.confidence * 100)}%</p>
                </div>
                <div className="col-span-2 sm:col-span-3">
                  <p className="text-xs text-slate-500">Intent</p>
                  <p className="font-medium text-slate-800">{detail.analysis.intent}</p>
                </div>
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-500">
                Not analyzed yet.{" "}
                <button
                  onClick={() => emailsApi.analyze(emailId).then(load)}
                  className="font-medium text-brand-600 hover:underline"
                >
                  Run analysis
                </button>
              </p>
            )}
          </div>

          {detail.draft ? (
            <DraftPanel draft={detail.draft} onChange={(d) => setDetail({ ...detail, draft: d })} />
          ) : detail.analysis?.requires_reply ? (
            <div className="rounded-xl border border-slate-200 bg-white p-5 text-center">
              <p className="text-sm text-slate-600">This email needs a reply, but no draft has been generated yet.</p>
              <button
                onClick={handleGenerateReply}
                disabled={generating}
                className="mt-3 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {generating ? "Generating…" : "Generate reply"}
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </ProtectedShell>
  );
}

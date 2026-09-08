"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ProtectedShell } from "@/components/ProtectedShell";
import { GmailStatusBadge } from "@/components/GmailStatusBadge";
import { useGmailStatus } from "@/hooks/useGmailStatus";
import { authApi, dashboardApi } from "@/services/api";
import type { DashboardStats, Session } from "@/types";

const STAT_CARDS: { key: keyof DashboardStats; label: string }[] = [
  { key: "total_emails", label: "Total Emails" },
  { key: "needs_reply", label: "Needs Reply" },
  { key: "ai_drafts", label: "AI Drafts" },
  { key: "pending_approval", label: "Pending Approval" },
  { key: "sent_replies", label: "Sent Replies" },
  { key: "auto_replies", label: "Auto Replies" },
  { key: "failed_processing", label: "Failed Processing" },
];

export default function DashboardPage() {
  const { status, loading } = useGmailStatus();
  const [profile, setProfile] = useState<Session | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);

  useEffect(() => {
    authApi.getSession().then(setProfile).catch(() => setProfile(null));
    dashboardApi
      .getStats()
      .then(setStats)
      .catch(() => setStatsError("Couldn't load stats right now."));
  }, []);

  return (
    <ProtectedShell>
      <h1 className="text-2xl font-semibold text-slate-900">
        Welcome{profile?.full_name ? `, ${profile.full_name}` : ""}
      </h1>
      <p className="mt-1 text-sm text-slate-600">
        {profile?.email ?? "Loading your account…"}
      </p>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-medium text-slate-900">Gmail connection</h2>
            <p className="mt-1 text-sm text-slate-600">
              Required before AI Mail Assistant can read or reply to your email.
            </p>
          </div>
          {!loading && status && <GmailStatusBadge status={status.status} />}
        </div>
        {status?.status !== "connected" && (
          <Link
            href="/settings/gmail"
            className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline"
          >
            Go to Gmail settings →
          </Link>
        )}
      </div>

      <h2 className="mt-8 text-lg font-medium text-slate-900">Overview</h2>
      {statsError && <p className="mt-2 text-sm text-red-600">{statsError}</p>}
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {STAT_CARDS.map((card) => (
          <div key={card.key} className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{card.label}</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">
              {stats ? stats[card.key] : <span className="text-slate-300">—</span>}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <Link
          href="/inbox"
          className="rounded-xl border border-slate-200 bg-white p-5 transition hover:border-brand-300 hover:shadow-sm"
        >
          <h3 className="font-medium text-slate-900">Inbox</h3>
          <p className="mt-1 text-sm text-slate-600">Browse and search your synced emails.</p>
        </Link>
        <Link
          href="/drafts"
          className="rounded-xl border border-slate-200 bg-white p-5 transition hover:border-brand-300 hover:shadow-sm"
        >
          <h3 className="font-medium text-slate-900">Drafts</h3>
          <p className="mt-1 text-sm text-slate-600">Review, edit, and approve AI-generated replies.</p>
        </Link>
      </div>
    </ProtectedShell>
  );
}

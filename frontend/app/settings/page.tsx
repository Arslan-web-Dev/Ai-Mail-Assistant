"use client";

import Link from "next/link";

import { ProtectedShell } from "@/components/ProtectedShell";

const SECTIONS = [
  { href: "/settings/gmail", title: "Gmail", desc: "Connect or disconnect your Gmail account." },
  { href: "/settings/ai", title: "AI", desc: "Tone, reply style, and model preferences." },
  { href: "/settings/automation", title: "Automation", desc: "Auto-reply rules and safety thresholds." },
  { href: "/settings/profile", title: "Profile", desc: "Your name, signature, and account details." },
];

export default function SettingsPage() {
  return (
    <ProtectedShell>
      <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {SECTIONS.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="rounded-xl border border-slate-200 bg-white p-5 transition hover:border-brand-300 hover:shadow-sm"
          >
            <h2 className="font-medium text-slate-900">{s.title}</h2>
            <p className="mt-1 text-sm text-slate-600">{s.desc}</p>
          </Link>
        ))}
      </div>
    </ProtectedShell>
  );
}

"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/hooks/useAuth";
import { signOut } from "@/services/authService";
import { NotificationBell } from "@/components/NotificationBell";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/inbox", label: "Inbox" },
  { href: "/drafts", label: "Drafts" },
  { href: "/sent", label: "Sent" },
  { href: "/analytics", label: "Analytics" },
  { href: "/settings/gmail", label: "Settings" },
];

export function ProtectedShell({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !session) {
      router.replace("/login");
    }
  }, [loading, session, router]);

  if (loading || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">
        Loading…
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <nav className="flex gap-5 text-sm font-medium text-slate-600">
            {NAV_LINKS.map((link) => (
              <Link key={link.href} href={link.href} className="hover:text-brand-600">
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-4">
            <NotificationBell />
            <button
              onClick={() => signOut().then(() => router.replace("/login"))}
              className="text-sm font-medium text-slate-500 hover:text-slate-800"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  );
}

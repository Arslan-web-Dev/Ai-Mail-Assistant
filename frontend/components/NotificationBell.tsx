"use client";

import { useEffect, useRef, useState } from "react";

import { notificationsApi } from "@/services/api";
import type { AppNotification } from "@/types";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const refreshCount = () => {
    notificationsApi
      .unreadCount()
      .then((r) => setUnreadCount(r.count))
      .catch(() => {});
  };

  useEffect(() => {
    refreshCount();
    const interval = setInterval(refreshCount, 60_000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const handleOpen = () => {
    setOpen((v) => !v);
    if (!open) {
      setLoading(true);
      notificationsApi
        .list()
        .then((page) => setItems(page.items as AppNotification[]))
        .finally(() => setLoading(false));
    }
  };

  const handleMarkAllRead = async () => {
    await notificationsApi.markAllRead();
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
  };

  const handleMarkRead = async (id: string) => {
    await notificationsApi.markRead(id);
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
    refreshCount();
  };

  const handleDelete = async (id: string) => {
    await notificationsApi.remove(id);
    setItems((prev) => prev.filter((n) => n.id !== id));
    refreshCount();
  };

  return (
    <div className="relative" ref={ref}>
      <button onClick={handleOpen} className="relative rounded-full p-1.5 text-slate-500 hover:bg-slate-100" aria-label="Notifications">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-semibold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 w-80 rounded-xl border border-slate-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
            <p className="text-sm font-medium text-slate-900">Notifications</p>
            {items.some((n) => !n.is_read) && (
              <button onClick={handleMarkAllRead} className="text-xs font-medium text-brand-600 hover:underline">
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {loading ? (
              <p className="px-4 py-6 text-center text-sm text-slate-400">Loading…</p>
            ) : items.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-slate-400">You're all caught up.</p>
            ) : (
              items.map((n) => (
                <div
                  key={n.id}
                  className={`flex items-start gap-2 border-b border-slate-50 px-4 py-2.5 text-sm ${n.is_read ? "text-slate-500" : "bg-brand-50/40 text-slate-800"}`}
                >
                  <div className="min-w-0 flex-1">
                    <p>{n.message}</p>
                    <p className="mt-0.5 text-xs text-slate-400">{timeAgo(n.created_at)}</p>
                  </div>
                  <div className="flex flex-shrink-0 flex-col items-end gap-1">
                    {!n.is_read && (
                      <button onClick={() => handleMarkRead(n.id)} className="text-xs text-brand-600 hover:underline">
                        Read
                      </button>
                    )}
                    <button onClick={() => handleDelete(n.id)} className="text-xs text-slate-400 hover:text-red-600">
                      Delete
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

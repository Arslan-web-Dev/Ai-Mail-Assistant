"use client";

import { useEffect, useState } from "react";

import { ProtectedShell } from "@/components/ProtectedShell";
import { ApiError, automationApi } from "@/services/api";
import type { AutomationSettings } from "@/types";

const CATEGORY_OPTIONS = [
  "job",
  "internship",
  "business",
  "meeting",
  "networking",
  "customer_support",
  "university",
  "personal",
  "newsletter",
  "notification",
];

function toggleInList(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

export default function AutomationSettingsPage() {
  const [settings, setSettings] = useState<AutomationSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = () => {
    setLoading(true);
    automationApi
      .getSettings()
      .then(setSettings)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load settings"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const save = async (updates: Partial<AutomationSettings>) => {
    if (!settings) return;
    const next = { ...settings, ...updates };
    setSettings(next);
    setSaving(true);
    setError(null);
    try {
      const result = await automationApi.updateSettings(updates);
      setSettings(result);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save");
      load(); // revert to server truth on failure
    } finally {
      setSaving(false);
    }
  };

  return (
    <ProtectedShell>
      <h1 className="text-2xl font-semibold text-slate-900">Automation settings</h1>
      <p className="mt-1 text-sm text-slate-600">
        Control when AI Mail Assistant is allowed to send a reply automatically, without your review.
        Legal, financial, medical, security, and other sensitive emails always require your manual approval —
        this can't be turned off.
      </p>

      {loading ? (
        <p className="mt-6 text-sm text-slate-500">Loading…</p>
      ) : error && !settings ? (
        <p className="mt-6 text-sm text-red-600">{error}</p>
      ) : settings ? (
        <div className="mt-6 space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-medium text-slate-900">Enable automation</h2>
                <p className="mt-1 text-sm text-slate-600">
                  When off, every draft waits for your manual approval — nothing is ever auto-sent.
                </p>
              </div>
              <label className="relative inline-flex cursor-pointer items-center">
                <input
                  type="checkbox"
                  checked={settings.auto_reply_enabled}
                  onChange={(e) => save({ auto_reply_enabled: e.target.checked })}
                  className="peer sr-only"
                />
                <div className="h-6 w-11 rounded-full bg-slate-200 peer-checked:bg-brand-600 peer-focus:outline-none after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all peer-checked:after:translate-x-full" />
              </label>
            </div>

            {settings.auto_reply_enabled && (
              <div className="mt-4 border-t border-slate-100 pt-4">
                <button
                  onClick={() => save({ paused: !settings.paused })}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  {settings.paused ? "Resume automation" : "Pause automation"}
                </button>
                {settings.paused && (
                  <span className="ml-2 text-xs font-medium text-amber-700">Currently paused</span>
                )}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="font-medium text-slate-900">Confidence &amp; risk</h2>
            <div className="mt-3">
              <label className="text-sm text-slate-700">
                Minimum AI confidence to auto-send: {Math.round(settings.minimum_ai_confidence * 100)}%
              </label>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(settings.minimum_ai_confidence * 100)}
                onChange={(e) => save({ minimum_ai_confidence: Number(e.target.value) / 100 })}
                className="mt-2 w-full"
              />
            </div>
            <label className="mt-4 flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={settings.require_approval_for_medium_risk}
                onChange={(e) => save({ require_approval_for_medium_risk: e.target.checked })}
              />
              Require approval for medium-risk emails
            </label>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="font-medium text-slate-900">Categories</h2>
            <p className="mt-1 text-sm text-slate-600">
              Optionally restrict auto-send to specific categories (allowed), or exclude categories entirely (blocked).
            </p>
            <div className="mt-3">
              <p className="text-xs font-medium text-slate-500">Allowed (empty = all categories)</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {CATEGORY_OPTIONS.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => save({ allowed_categories: toggleInList(settings.allowed_categories, cat) })}
                    className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                      settings.allowed_categories.includes(cat)
                        ? "border-green-500 bg-green-50 text-green-700"
                        : "border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>
            <div className="mt-4">
              <p className="text-xs font-medium text-slate-500">Blocked</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {CATEGORY_OPTIONS.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => save({ blocked_categories: toggleInList(settings.blocked_categories, cat) })}
                    className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                      settings.blocked_categories.includes(cat)
                        ? "border-red-500 bg-red-50 text-red-700"
                        : "border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="font-medium text-slate-900">Limits &amp; hours</h2>
            <div className="mt-3">
              <label className="text-sm text-slate-700">Daily auto-reply limit (0 = unlimited)</label>
              <input
                type="number"
                min={0}
                max={1000}
                value={settings.daily_reply_limit}
                onChange={(e) => save({ daily_reply_limit: Number(e.target.value) })}
                className="mt-1 w-32 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>

            <label className="mt-4 flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={settings.business_hours_enabled}
                onChange={(e) => save({ business_hours_enabled: e.target.checked })}
              />
              Only auto-send during business hours
            </label>
            {settings.business_hours_enabled && (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-700">
                <input
                  type="time"
                  value={settings.business_hours_start}
                  onChange={(e) => save({ business_hours_start: e.target.value })}
                  className="rounded-lg border border-slate-300 px-2 py-1"
                />
                <span>to</span>
                <input
                  type="time"
                  value={settings.business_hours_end}
                  onChange={(e) => save({ business_hours_end: e.target.value })}
                  className="rounded-lg border border-slate-300 px-2 py-1"
                />
                <input
                  type="text"
                  value={settings.business_hours_timezone}
                  onChange={(e) => save({ business_hours_timezone: e.target.value })}
                  placeholder="e.g. America/New_York"
                  className="rounded-lg border border-slate-300 px-2 py-1"
                />
              </div>
            )}
          </div>

          <div className="flex items-center gap-3 text-sm">
            {saving && <span className="text-slate-500">Saving…</span>}
            {saved && <span className="text-green-600">Saved</span>}
            {error && <span className="text-red-600">{error}</span>}
          </div>
        </div>
      ) : null}
    </ProtectedShell>
  );
}

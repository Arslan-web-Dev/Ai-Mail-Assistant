"use client";

import { useEffect, useState } from "react";

import { ProtectedShell } from "@/components/ProtectedShell";
import { ApiError, aiPreferencesApi } from "@/services/api";
import type { AIPreferences } from "@/types";

const TONES = ["Professional", "Friendly", "Formal", "Concise", "Confident"];
const LENGTHS: AIPreferences["reply_length"][] = ["short", "medium", "long"];

export default function AiSettingsPage() {
  const [prefs, setPrefs] = useState<AIPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [preview, setPreview] = useState<{ subject: string | null; reply: string | null } | null>(null);
  const [previewing, setPreviewing] = useState(false);

  useEffect(() => {
    aiPreferencesApi
      .get()
      .then(setPrefs)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load AI settings"))
      .finally(() => setLoading(false));
  }, []);

  const save = async (updates: Partial<AIPreferences>) => {
    if (!prefs) return;
    const next = { ...prefs, ...updates };
    setPrefs(next);
    setSaving(true);
    try {
      const result = await aiPreferencesApi.update(updates);
      setPrefs(result);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const runPreview = async () => {
    if (!prefs) return;
    setPreviewing(true);
    try {
      const result = await aiPreferencesApi.preview({
        tone: prefs.tone,
        signature: prefs.signature ?? undefined,
        custom_instructions: prefs.custom_instructions ?? undefined,
      });
      setPreview(result);
    } catch (err) {
      setPreview({ subject: null, reply: err instanceof ApiError ? err.message : "Preview failed" });
    } finally {
      setPreviewing(false);
    }
  };

  return (
    <ProtectedShell>
      <h1 className="text-2xl font-semibold text-slate-900">AI settings</h1>
      <p className="mt-1 text-sm text-slate-600">
        These preferences shape tone and style only — they can never override AI Mail Assistant's built-in
        safety rules (never inventing facts, never making unauthorized promises, and so on).
      </p>

      {loading ? (
        <p className="mt-6 text-sm text-slate-500">Loading…</p>
      ) : prefs ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="font-medium text-slate-900">Tone &amp; length</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {TONES.map((t) => (
                  <button
                    key={t}
                    onClick={() => save({ tone: t })}
                    className={`rounded-full border px-3 py-1 text-xs font-medium ${
                      prefs.tone === t ? "border-brand-500 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <div className="mt-4 flex gap-2">
                {LENGTHS.map((l) => (
                  <button
                    key={l}
                    onClick={() => save({ reply_length: l })}
                    className={`rounded-full border px-3 py-1 text-xs font-medium capitalize ${
                      prefs.reply_length === l ? "border-brand-500 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="font-medium text-slate-900">Signature</h2>
              <textarea
                value={prefs.signature ?? ""}
                onChange={(e) => setPrefs({ ...prefs, signature: e.target.value })}
                onBlur={() => save({ signature: prefs.signature })}
                rows={3}
                placeholder="Best,&#10;Alex"
                className="mt-2 w-full rounded-lg border border-slate-300 p-2.5 text-sm focus:border-brand-500 focus:outline-none"
              />
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="font-medium text-slate-900">Custom instructions</h2>
              <p className="mt-1 text-xs text-slate-500">
                Style or content guidance only — cannot override safety rules.
              </p>
              <textarea
                value={prefs.custom_instructions ?? ""}
                onChange={(e) => setPrefs({ ...prefs, custom_instructions: e.target.value })}
                onBlur={() => save({ custom_instructions: prefs.custom_instructions })}
                rows={4}
                placeholder="e.g. Keep replies under 3 sentences when possible."
                className="mt-2 w-full rounded-lg border border-slate-300 p-2.5 text-sm focus:border-brand-500 focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-3 text-sm">
              {saving && <span className="text-slate-500">Saving…</span>}
              {saved && <span className="text-green-600">Saved</span>}
              {error && <span className="text-red-600">{error}</span>}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <h2 className="font-medium text-slate-900">Preview</h2>
              <button
                onClick={runPreview}
                disabled={previewing}
                className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {previewing ? "Generating…" : "Preview a reply"}
              </button>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Runs your current settings against a sample email — nothing is sent, no real inbox is touched.
            </p>
            {preview && (
              <div className="mt-4 rounded-lg bg-slate-50 p-3">
                {preview.subject && <p className="text-sm font-medium text-slate-700">Subject: {preview.subject}</p>}
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{preview.reply}</p>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </ProtectedShell>
  );
}

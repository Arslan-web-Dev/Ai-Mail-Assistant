"use client";

import { useEffect, useState } from "react";

import { ProtectedShell } from "@/components/ProtectedShell";
import { ApiError, profileApi } from "@/services/api";
import type { Profile } from "@/types";

export default function ProfileSettingsPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [skillsInput, setSkillsInput] = useState("");

  useEffect(() => {
    profileApi
      .get()
      .then((p) => {
        setProfile(p);
        setSkillsInput((p.skills || []).join(", "));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load profile"))
      .finally(() => setLoading(false));
  }, []);

  const save = async (updates: Partial<Profile>) => {
    setSaving(true);
    setError(null);
    try {
      const result = await profileApi.update(updates);
      setProfile(result);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <ProtectedShell>
        <p className="text-sm text-slate-500">Loading…</p>
      </ProtectedShell>
    );
  }

  if (!profile) {
    return (
      <ProtectedShell>
        <p className="text-sm text-red-600">{error}</p>
      </ProtectedShell>
    );
  }

  return (
    <ProtectedShell>
      <h1 className="text-2xl font-semibold text-slate-900">Profile</h1>
      <p className="mt-1 text-sm text-slate-600">
        Used as context when generating replies — never invented, only what you provide here.
      </p>

      <div className="mt-6 space-y-4 rounded-xl border border-slate-200 bg-white p-6">
        <div>
          <label className="text-sm text-slate-500">Email</label>
          <p className="text-sm text-slate-800">{profile.email}</p>
        </div>

        <div>
          <label className="text-sm text-slate-500">Name</label>
          <input
            defaultValue={profile.full_name ?? ""}
            onBlur={(e) => save({ full_name: e.target.value })}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="text-sm text-slate-500">Professional title</label>
          <input
            defaultValue={profile.professional_title ?? ""}
            onBlur={(e) => save({ professional_title: e.target.value })}
            placeholder="e.g. Senior Product Manager"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="text-sm text-slate-500">Company</label>
          <input
            defaultValue={profile.company ?? ""}
            onBlur={(e) => save({ company: e.target.value })}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="text-sm text-slate-500">Skills (comma-separated)</label>
          <input
            value={skillsInput}
            onChange={(e) => setSkillsInput(e.target.value)}
            onBlur={() =>
              save({ skills: skillsInput.split(",").map((s) => s.trim()).filter(Boolean) })
            }
            placeholder="e.g. Product Strategy, SQL, Figma"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="text-sm text-slate-500">Experience</label>
          <textarea
            defaultValue={profile.experience ?? ""}
            onBlur={(e) => save({ experience: e.target.value })}
            rows={4}
            placeholder="A short summary of your background."
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-3 pt-2 text-sm">
          {saving && <span className="text-slate-500">Saving…</span>}
          {saved && <span className="text-green-600">Saved</span>}
          {error && <span className="text-red-600">{error}</span>}
        </div>
      </div>

      <p className="mt-4 text-xs text-slate-500">
        Your Gmail OAuth connection is managed separately under Settings → Gmail. Credentials are never shown here.
      </p>
    </ProtectedShell>
  );
}

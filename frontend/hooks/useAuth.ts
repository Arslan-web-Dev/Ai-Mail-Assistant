"use client";

import { useEffect, useState } from "react";
import type { Session as SupabaseSession } from "@supabase/supabase-js";

import { supabase } from "@/utils/supabaseClient";

interface AuthState {
  session: SupabaseSession | null;
  loading: boolean;
}

/**
 * Tracks the Supabase auth session in the browser. This only tells you
 * whether *a* session exists client-side for UI purposes (redirects,
 * showing the right nav, etc). It is never used by the backend to decide
 * access — the backend independently re-verifies the JWT on every request.
 */
export function useAuth(): AuthState {
  const [session, setSession] = useState<SupabaseSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
    });

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  return { session, loading };
}

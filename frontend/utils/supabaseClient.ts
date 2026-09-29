import { createClient } from "@supabase/supabase-js";

// Only the PUBLIC anon key is ever used in the browser. It is safe to
// expose — Postgres Row Level Security (see backend/database/schema.sql)
// is what actually protects user data, not secrecy of this key.
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL as string;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY as string;

if (!supabaseUrl || !supabaseAnonKey) {
  // eslint-disable-next-line no-console
  console.warn(
    "NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY are not set. " +
      "Copy .env.example to frontend/.env.local and fill them in."
  );
}

export const supabase = createClient(supabaseUrl ?? "", supabaseAnonKey ?? "");

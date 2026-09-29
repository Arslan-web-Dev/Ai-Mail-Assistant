-- AI Mail Assistant — Supabase schema (Module 1 & 2)
-- Run this in the Supabase SQL editor.
-- Auth/users are managed by Supabase Auth (auth.users); we only store our
-- own app-specific tables here, keyed by auth.users.id.

-- ---------------------------------------------------------------------
-- profiles: one row per authenticated user, app-specific profile data
-- ---------------------------------------------------------------------
create table if not exists public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    email text not null,
    full_name text,
    avatar_url text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "profiles_select_own"
    on public.profiles for select
    using (auth.uid() = id);

create policy "profiles_update_own"
    on public.profiles for update
    using (auth.uid() = id);

-- profile rows are created by the backend (service role) right after first
-- login, so no public insert policy is needed.

-- ---------------------------------------------------------------------
-- gmail_connections: one row per user, holds encrypted OAuth tokens
-- Tokens are encrypted at the application layer (Fernet) before storage —
-- this table never holds a usable plaintext token even for the service role.
-- ---------------------------------------------------------------------
create table if not exists public.gmail_connections (
    user_id uuid primary key references auth.users (id) on delete cascade,
    gmail_email text not null,
    encrypted_access_token text not null,
    encrypted_refresh_token text not null,
    scopes text not null,
    token_expiry timestamptz not null,
    status text not null default 'connected', -- connected | disconnected | error
    last_error text,
    connected_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.gmail_connections enable row level security;

create policy "gmail_connections_select_own"
    on public.gmail_connections for select
    using (auth.uid() = user_id);

-- Inserts/updates/deletes to this table are performed exclusively by the
-- backend using the service-role key (never directly by the client), so no
-- insert/update/delete policies are granted to authenticated users.

-- ---------------------------------------------------------------------
-- oauth_states: short-lived, single-use CSRF state tokens for the OAuth flow
-- ---------------------------------------------------------------------
create table if not exists public.oauth_states (
    state text primary key,
    user_id uuid not null references auth.users (id) on delete cascade,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null
);

alter table public.oauth_states enable row level security;
-- No client policies: only the backend (service role) reads/writes this table.


-- =======================================================================
-- MODULE 3 — Email sync tables
--
-- Note: `users` (spec) is deliberately NOT a separate table here — we
-- extend the existing `profiles` table from Module 2 instead, to avoid
-- duplicating identity data that already lives in auth.users + profiles.
-- Likewise `gmail_accounts` (spec) is already covered by the
-- `gmail_connections` table created in Module 2; we extend it below
-- rather than creating a duplicate table, per "do not rewrite working
-- code unnecessarily".
-- =======================================================================

-- Extend profiles with the watch/sync bookkeeping fields email sync needs.
alter table public.profiles
    add column if not exists last_history_id text,
    add column if not exists watch_expiration timestamptz;

-- Extend gmail_connections (already the `gmail_accounts` table) with
-- push-notification bookkeeping.
alter table public.gmail_connections
    add column if not exists watch_history_id text,
    add column if not exists watch_expiration timestamptz;

-- ---------------------------------------------------------------------
-- email_threads: one row per Gmail conversation thread
-- ---------------------------------------------------------------------
create table if not exists public.email_threads (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    gmail_thread_id text not null,
    subject text,
    last_message_at timestamptz,
    message_count integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, gmail_thread_id)
);

alter table public.email_threads enable row level security;

create policy "email_threads_select_own"
    on public.email_threads for select
    using (auth.uid() = user_id);

create index if not exists idx_email_threads_user on public.email_threads (user_id);

-- ---------------------------------------------------------------------
-- emails: one row per synced Gmail message
-- ---------------------------------------------------------------------
create table if not exists public.emails (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    thread_id uuid references public.email_threads (id) on delete set null,
    gmail_message_id text not null,
    gmail_thread_id text not null,
    sender text not null,
    recipient text,
    subject text,
    body_text text,          -- sanitized plain-text body (safe to display/feed to AI)
    body_html_sanitized text, -- sanitized HTML for rendering (scripts/handlers stripped)
    snippet text,
    labels text[],
    has_attachments boolean not null default false,
    attachment_metadata jsonb, -- [{filename, mime_type, size, attachment_id}], never auto-downloaded content
    received_at timestamptz,
    is_read boolean not null default false,
    requires_reply boolean,
    processing_status text not null default 'pending',
        -- pending | parsed | analyzed | failed | ignored
    created_at timestamptz not null default now(),

    -- Gmail message IDs are unique per mailbox — this is the core
    -- duplicate-prevention constraint for email sync.
    unique (user_id, gmail_message_id)
);

alter table public.emails enable row level security;

create policy "emails_select_own"
    on public.emails for select
    using (auth.uid() = user_id);

create index if not exists idx_emails_user on public.emails (user_id);
create index if not exists idx_emails_user_received on public.emails (user_id, received_at desc);
create index if not exists idx_emails_thread on public.emails (thread_id);
create index if not exists idx_emails_status on public.emails (user_id, processing_status);
create index if not exists idx_emails_gmail_thread on public.emails (user_id, gmail_thread_id);

-- ---------------------------------------------------------------------
-- ai_analyses: one row per email, AI classification results (Module 4)
-- ---------------------------------------------------------------------
create table if not exists public.ai_analyses (
    id uuid primary key default gen_random_uuid(),
    email_id uuid not null references public.emails (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    category text,       -- job | internship | business | meeting | ... (see Module 4)
    intent text,
    priority text,        -- low | medium | high | urgent
    sentiment text,
    requires_reply boolean,
    sensitivity_level text, -- LOW | MEDIUM | HIGH | CRITICAL
    confidence numeric(4,3),
    raw_response jsonb,
    created_at timestamptz not null default now(),
    unique (email_id)
);

alter table public.ai_analyses enable row level security;

create policy "ai_analyses_select_own"
    on public.ai_analyses for select
    using (auth.uid() = user_id);

create index if not exists idx_ai_analyses_user on public.ai_analyses (user_id);
create index if not exists idx_ai_analyses_email on public.ai_analyses (email_id);

-- ---------------------------------------------------------------------
-- email_drafts: AI-generated replies awaiting review (Module 4 & 5)
-- ---------------------------------------------------------------------
create table if not exists public.email_drafts (
    id uuid primary key default gen_random_uuid(),
    email_id uuid not null references public.emails (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    generated_content text not null,
    edited_content text,
    subject text,
    status text not null default 'generating',
        -- generating | ready | edited | approved | rejected | sent | failed
    confidence numeric(4,3),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.email_drafts enable row level security;

create policy "email_drafts_select_own"
    on public.email_drafts for select
    using (auth.uid() = user_id);

create index if not exists idx_email_drafts_user on public.email_drafts (user_id);
create index if not exists idx_email_drafts_email on public.email_drafts (email_id);
create index if not exists idx_email_drafts_status on public.email_drafts (user_id, status);

-- ---------------------------------------------------------------------
-- sent_emails: record of replies actually sent (manual or automated)
-- ---------------------------------------------------------------------
create table if not exists public.sent_emails (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    draft_id uuid references public.email_drafts (id) on delete set null,
    email_id uuid references public.emails (id) on delete set null,
    gmail_message_id text,   -- the ID Gmail assigned to the sent reply
    gmail_thread_id text,
    recipient text not null,
    subject text,
    body text not null,
    sent_via text not null default 'manual', -- manual | auto
    created_at timestamptz not null default now(),
    unique (user_id, gmail_message_id)
);

alter table public.sent_emails enable row level security;

create policy "sent_emails_select_own"
    on public.sent_emails for select
    using (auth.uid() = user_id);

create index if not exists idx_sent_emails_user on public.sent_emails (user_id);

-- ---------------------------------------------------------------------
-- automation_rules: user-defined auto-reply rules (Module 6)
-- ---------------------------------------------------------------------
create table if not exists public.automation_rules (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    rule_name text not null,
    enabled boolean not null default true,
    conditions jsonb not null default '{}'::jsonb,
    action text not null default 'manual_review', -- auto_send | manual_review | block
    requires_approval boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.automation_rules enable row level security;

create policy "automation_rules_select_own"
    on public.automation_rules for select
    using (auth.uid() = user_id);

create index if not exists idx_automation_rules_user on public.automation_rules (user_id);

-- ---------------------------------------------------------------------
-- user_ai_preferences: one row per user, AI writing preferences (Module 4/7)
-- ---------------------------------------------------------------------
create table if not exists public.user_ai_preferences (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references auth.users (id) on delete cascade,
    tone text not null default 'Professional',
    language text not null default 'en',
    signature text,
    custom_instructions text,
    auto_reply_enabled boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.user_ai_preferences enable row level security;

create policy "user_ai_preferences_select_own"
    on public.user_ai_preferences for select
    using (auth.uid() = user_id);

-- ---------------------------------------------------------------------
-- email_processing_logs: sync/parsing/AI pipeline logs, for debugging
-- ---------------------------------------------------------------------
create table if not exists public.email_processing_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    email_id uuid references public.emails (id) on delete cascade,
    stage text not null, -- sync | parse | ai_analysis | reply_generation | send
    status text not null, -- success | failed | retrying
    message text,
    created_at timestamptz not null default now()
);

alter table public.email_processing_logs enable row level security;

create policy "email_processing_logs_select_own"
    on public.email_processing_logs for select
    using (auth.uid() = user_id);

create index if not exists idx_processing_logs_user on public.email_processing_logs (user_id, created_at desc);
create index if not exists idx_processing_logs_email on public.email_processing_logs (email_id);

-- ---------------------------------------------------------------------
-- notifications: in-app notifications (Module 7)
-- ---------------------------------------------------------------------
create table if not exists public.notifications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    type text not null,
    message text not null,
    is_read boolean not null default false,
    metadata jsonb,
    created_at timestamptz not null default now()
);

alter table public.notifications enable row level security;

create policy "notifications_select_own"
    on public.notifications for select
    using (auth.uid() = user_id);

create index if not exists idx_notifications_user on public.notifications (user_id, is_read, created_at desc);

-- ---------------------------------------------------------------------
-- audit_logs: security-relevant actions (send, disconnect, rule changes)
-- ---------------------------------------------------------------------
create table if not exists public.audit_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    action text not null,
    details jsonb,
    created_at timestamptz not null default now()
);

alter table public.audit_logs enable row level security;

create policy "audit_logs_select_own"
    on public.audit_logs for select
    using (auth.uid() = user_id);

create index if not exists idx_audit_logs_user on public.audit_logs (user_id, created_at desc);

-- All insert/update/delete on the Module 3 tables above is performed by the
-- backend using the service-role key (never directly by the client), so no
-- write policies are granted to authenticated users — matching the pattern
-- already established for gmail_connections/oauth_states in Module 2.


-- =======================================================================
-- MODULE 4 — AI analysis + reply generation additions
-- =======================================================================

-- Whether the model itself (or the sensitivity classification) flagged
-- this draft as needing human review before it could ever be auto-sent.
-- Module 6's safety layer reads this alongside ai_analyses.sensitivity_level.
alter table public.email_drafts
    add column if not exists requires_review boolean not null default false;


-- =======================================================================
-- MODULE 5 — Dashboard + draft management + sending additions
-- =======================================================================

-- RFC 5322 Message-ID header of the original email, needed to set proper
-- In-Reply-To / References headers on the reply so Gmail (and other
-- clients) thread it correctly.
alter table public.emails
    add column if not exists rfc_message_id text;

-- One sent record per draft — a second send attempt for the same draft
-- (e.g. a double-click race) hits this constraint and is treated as
-- "already sent" rather than sending twice. draft_id is nullable in the
-- table definition for flexibility (e.g. future non-draft sends), so this
-- is a partial unique index rather than a plain column constraint.
create unique index if not exists idx_sent_emails_draft_id
    on public.sent_emails (draft_id)
    where draft_id is not null;

-- Supports ILIKE search on subject/sender/body without a full-text setup;
-- swap for a GIN/tsvector index later if search volume grows.
create index if not exists idx_emails_subject_trgm on public.emails (subject);


-- =======================================================================
-- MODULE 6 — Automation + safety additions
-- =======================================================================

-- One row per user: the global automation configuration read by
-- services/safety_engine.py + automation_service.py. Distinct from the
-- `automation_rules` table (Module 3), which is for user-authored named
-- rules (a more advanced/optional feature) — this table holds the core
-- toggles every automated decision is checked against.
create table if not exists public.automation_settings (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references auth.users (id) on delete cascade,
    auto_reply_enabled boolean not null default false,
    paused boolean not null default false,
    minimum_ai_confidence numeric(4,3) not null default 0.900,
    allowed_categories text[] not null default '{}',
    blocked_categories text[] not null default '{spam}',
    require_approval_for_medium_risk boolean not null default true,
    daily_reply_limit integer not null default 20,
    business_hours_enabled boolean not null default false,
    business_hours_start text not null default '09:00',
    business_hours_end text not null default '18:00',
    business_hours_timezone text not null default 'UTC',
    signature_enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.automation_settings enable row level security;

create policy "automation_settings_select_own"
    on public.automation_settings for select
    using (auth.uid() = user_id);

-- Writes go through the backend (service role) only, same pattern as
-- every other settings/state table in this schema.

create index if not exists idx_sent_emails_user_auto_created
    on public.sent_emails (user_id, sent_via, created_at);


-- =======================================================================
-- MODULE 7 — Settings + analytics + notifications additions
-- =======================================================================

-- Profile fields used as context for AI reply generation and shown on the
-- Profile settings page. Extends `profiles` again, per the Module 3
-- decision to keep one user-identity table rather than spawning new ones.
alter table public.profiles
    add column if not exists professional_title text,
    add column if not exists company text,
    add column if not exists skills text[] not null default '{}',
    add column if not exists experience text;

-- Reply length preference, shown on the AI settings page.
alter table public.user_ai_preferences
    add column if not exists reply_length text not null default 'medium';

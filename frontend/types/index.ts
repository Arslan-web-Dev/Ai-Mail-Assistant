export interface Session {
  id: string;
  email: string | null;
  full_name: string | null;
  avatar_url: string | null;
}

export type GmailConnectionStatus =
  | "connected"
  | "disconnected"
  | "connecting"
  | "error";

export interface GmailStatus {
  status: GmailConnectionStatus;
  gmail_email: string | null;
  connected_at: string | null;
  last_error: string | null;
}

export interface EmailSummary {
  id: string;
  gmail_message_id: string;
  gmail_thread_id: string;
  sender: string;
  recipient: string | null;
  subject: string | null;
  snippet: string | null;
  received_at: string | null;
  is_read: boolean;
  requires_reply: boolean | null;
  processing_status: string;
  has_attachments: boolean;
}

export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
}

export type EmailFilter =
  | "all"
  | "unread"
  | "needs_reply"
  | "drafts"
  | "sent"
  | "high_priority"
  | "job"
  | "business"
  | "meeting"
  | "personal";

export interface AIAnalysis {
  category: string;
  intent: string;
  priority: string;
  sentiment: string;
  requires_reply: boolean;
  sensitivity_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  confidence: number;
}

export type DraftStatus =
  | "generating"
  | "ready"
  | "edited"
  | "approved"
  | "rejected"
  | "sent"
  | "failed";

export interface Draft {
  id: string;
  email_id: string;
  user_id: string;
  generated_content: string;
  edited_content: string | null;
  subject: string | null;
  status: DraftStatus;
  confidence: number | null;
  requires_review: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmailDetail {
  email: EmailSummary & { body_text?: string };
  analysis: AIAnalysis | null;
  draft: Draft | null;
}

export interface DashboardStats {
  total_emails: number;
  needs_reply: number;
  ai_drafts: number;
  pending_approval: number;
  sent_replies: number;
  auto_replies: number;
  failed_processing: number;
}

export interface AutomationSettings {
  auto_reply_enabled: boolean;
  paused: boolean;
  minimum_ai_confidence: number;
  allowed_categories: string[];
  blocked_categories: string[];
  require_approval_for_medium_risk: boolean;
  daily_reply_limit: number;
  business_hours_enabled: boolean;
  business_hours_start: string;
  business_hours_end: string;
  business_hours_timezone: string;
  signature_enabled: boolean;
}

export interface AnalyticsSummary {
  start: string;
  end: string;
  total_emails: number;
  emails_processed: number;
  replies_generated: number;
  replies_sent: number;
  auto_replies: number;
  manual_replies: number;
  rejected_drafts: number;
  failed_replies: number;
  average_processing_time_seconds: number | null;
  average_ai_confidence: number | null;
  category_breakdown: Record<string, number>;
  reply_activity: { date: string; count: number }[];
  automation_activity: Record<string, number>;
}

export type AnalyticsRange = "7d" | "30d" | "90d" | "custom";

export interface AppNotification {
  id: string;
  user_id: string;
  type: string;
  message: string;
  is_read: boolean;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface Profile {
  id: string;
  email: string | null;
  full_name: string | null;
  avatar_url: string | null;
  professional_title: string | null;
  company: string | null;
  skills: string[];
  experience: string | null;
}

export interface AIPreferences {
  tone: string;
  language: string;
  signature: string | null;
  custom_instructions: string | null;
  reply_length: "short" | "medium" | "long";
  auto_reply_enabled: boolean;
}

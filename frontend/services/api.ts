import { getAccessToken } from "@/services/authService";
import type {
  AIPreferences,
  AnalyticsRange,
  AnalyticsSummary,
  AppNotification,
  AutomationSettings,
  CursorPage,
  DashboardStats,
  Draft,
  EmailDetail,
  EmailFilter,
  EmailSummary,
  GmailStatus,
  Profile,
  Session,
} from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getAccessToken();
  if (!token) {
    throw new ApiError(401, "Not signed in");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const authApi = {
  getSession: () => request<Session>("/auth/session"),
};

export const gmailApi = {
  getAuthorizationUrl: () =>
    request<{ authorization_url: string }>("/gmail/connect"),
  getStatus: () => request<GmailStatus>("/gmail/status"),
  disconnect: () =>
    request<{ status: string }>("/gmail/disconnect", { method: "POST" }),
};

export interface ListEmailsParams {
  cursor?: string | null;
  limit?: number;
  search?: string;
  filter?: EmailFilter;
}

export const emailsApi = {
  list: ({ cursor, limit, search, filter }: ListEmailsParams = {}) => {
    const params = new URLSearchParams();
    if (cursor) params.set("cursor", cursor);
    if (limit) params.set("limit", String(limit));
    if (search) params.set("search", search);
    if (filter) params.set("filter", filter);
    const qs = params.toString();
    return request<CursorPage<EmailSummary>>(`/emails${qs ? `?${qs}` : ""}`);
  },
  getDetail: (emailId: string) => request<EmailDetail>(`/emails/${emailId}`),
  analyze: (emailId: string) =>
    request(`/emails/${emailId}/analyze`, { method: "POST" }),
  generateReply: (emailId: string) =>
    request<Draft>(`/emails/${emailId}/generate-reply`, { method: "POST" }),
};

export interface ListDraftsParams {
  cursor?: string | null;
  limit?: number;
  status?: string;
}

export const draftsApi = {
  list: ({ cursor, limit, status }: ListDraftsParams = {}) => {
    const params = new URLSearchParams();
    if (cursor) params.set("cursor", cursor);
    if (limit) params.set("limit", String(limit));
    if (status) params.set("status", status);
    const qs = params.toString();
    return request<CursorPage<Draft>>(`/drafts${qs ? `?${qs}` : ""}`);
  },
  get: (draftId: string) => request<Draft>(`/drafts/${draftId}`),
  update: (draftId: string, editedContent: string, subject?: string) =>
    request<Draft>(`/drafts/${draftId}`, {
      method: "PATCH",
      body: JSON.stringify({ edited_content: editedContent, subject }),
    }),
  regenerate: (draftId: string) =>
    request<Draft>(`/drafts/${draftId}/regenerate`, { method: "POST" }),
  reject: (draftId: string) =>
    request<Draft>(`/drafts/${draftId}/reject`, { method: "POST" }),
  approve: (draftId: string) =>
    request<Draft>(`/drafts/${draftId}/approve`, { method: "POST" }),
};

export const dashboardApi = {
  getStats: () => request<DashboardStats>("/dashboard/stats"),
};

export const automationApi = {
  getSettings: () => request<AutomationSettings>("/automation/settings"),
  updateSettings: (updates: Partial<AutomationSettings>) =>
    request<AutomationSettings>("/automation/settings", {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),
  pause: () => request<AutomationSettings>("/automation/pause", { method: "POST" }),
  resume: () => request<AutomationSettings>("/automation/resume", { method: "POST" }),
};

export const analyticsApi = {
  getSummary: (range: AnalyticsRange, start?: string, end?: string) => {
    const params = new URLSearchParams({ range });
    if (range === "custom" && start && end) {
      params.set("start", start);
      params.set("end", end);
    }
    return request<AnalyticsSummary>(`/analytics/summary?${params.toString()}`);
  },
};

export const notificationsApi = {
  list: (unreadOnly = false, cursor?: string | null) => {
    const params = new URLSearchParams();
    if (unreadOnly) params.set("unread_only", "true");
    if (cursor) params.set("cursor", cursor);
    const qs = params.toString();
    return request<CursorPage<AppNotification>>(`/notifications${qs ? `?${qs}` : ""}`);
  },
  unreadCount: () => request<{ count: number }>("/notifications/unread-count"),
  markRead: (id: string) => request(`/notifications/${id}/read`, { method: "POST" }),
  markAllRead: () => request("/notifications/read-all", { method: "POST" }),
  remove: (id: string) => request(`/notifications/${id}`, { method: "DELETE" }),
};

export const profileApi = {
  get: () => request<Profile>("/profile"),
  update: (updates: Partial<Profile>) =>
    request<Profile>("/profile", { method: "PATCH", body: JSON.stringify(updates) }),
};

export const aiPreferencesApi = {
  get: () => request<AIPreferences>("/ai/preferences"),
  update: (updates: Partial<AIPreferences>) =>
    request<AIPreferences>("/ai/preferences", { method: "PATCH", body: JSON.stringify(updates) }),
  preview: (overrides: { tone?: string; signature?: string; custom_instructions?: string }) =>
    request<{ subject: string | null; reply: string | null; error?: string }>("/ai/preview-reply", {
      method: "POST",
      body: JSON.stringify(overrides),
    }),
};

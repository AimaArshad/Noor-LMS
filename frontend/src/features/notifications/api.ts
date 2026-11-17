import { api } from "@/api/client";
import type { AppNotification, NotificationPage, ReadAllResult } from "@/types";

export const notificationsApi = {
  /** Newest first. `unread_count` covers ALL notifications, not just this page. */
  list: (limit: number) =>
    api.get<NotificationPage>("/notifications", { params: { limit } }).then((r) => r.data),

  /** Idempotent. */
  markRead: (id: string) =>
    api.patch<AppNotification>(`/notifications/${id}/read`).then((r) => r.data),

  markAllRead: () => api.post<ReadAllResult>("/notifications/read-all").then((r) => r.data),
};

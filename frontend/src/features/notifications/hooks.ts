import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useSocketStatus } from "@/api/ws";
import { notificationsApi } from "@/features/notifications/api";

/** Prefix used for invalidation: the WebSocket client invalidates ["notifications"]. */
export const notificationKeys = {
  all: ["notifications"] as const,
  list: (limit: number) => ["notifications", "list", { limit }] as const,
};

export function useNotifications(limit = 10) {
  const socketOpen = useSocketStatus((s) => s.status === "open");
  return useQuery({
    queryKey: notificationKeys.list(limit),
    queryFn: () => notificationsApi.list(limit),
    refetchOnWindowFocus: true,
    // Live pushes keep the cache fresh. Without a socket, poll once a minute.
    refetchInterval: socketOpen ? false : 60_000,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationKeys.all }),
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationKeys.all }),
  });
}

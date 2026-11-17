import { useEffect } from "react";

import { connectNotifications } from "@/api/ws";
import { useAuthStore } from "@/store/auth";

/** Keeps one notifications socket open while a user is signed in. Mount it once, in AppLayout. */
export function useNotificationSocket(): void {
  const userId = useAuthStore((s) => s.user?.id);
  useEffect(() => {
    if (!userId) return;
    return connectNotifications();
  }, [userId]);
}

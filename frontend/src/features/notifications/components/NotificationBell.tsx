import { Bell, Loader2 } from "lucide-react";
import { useEffect, useRef, useState, type FocusEvent } from "react";
import { useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { Button } from "@/components/ui/button";
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
} from "@/features/notifications/hooks";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AppNotification } from "@/types";

/** Backend links are app routes. Never navigate to anything else (e.g. `//evil.example`). */
function isInternalPath(link: string | null | undefined): link is string {
  return typeof link === "string" && link.startsWith("/") && !link.startsWith("//");
}

export function NotificationBell() {
  const navigate = useNavigate();
  const { data, isPending, isError, error, refetch } = useNotifications(10);
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllNotificationsRead();

  const [open, setOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const lastTopId = useRef<string | null | undefined>(undefined); // undefined = nothing loaded yet

  const unread = data?.unread_count ?? 0;
  const items = data?.items ?? [];

  // Tell screen-reader users when a NEW unread notification arrives (not on the first load).
  useEffect(() => {
    if (!data) return;
    const first = data.items[0];
    const topId = first?.id ?? null;
    if (lastTopId.current !== undefined && first && topId !== lastTopId.current && !first.is_read) {
      setAnnouncement(`New notification: ${first.title}`);
    }
    lastTopId.current = topId;
  }, [data]);

  // Close on outside click and on Escape (focus returns to the bell).
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  // Close when keyboard focus moves somewhere outside the bell and its panel.
  function onBlur(event: FocusEvent<HTMLDivElement>) {
    const next = event.relatedTarget as Node | null;
    if (next && !rootRef.current?.contains(next)) setOpen(false);
  }

  function onSelect(notification: AppNotification) {
    if (!notification.is_read) markRead.mutate(notification.id);
    setOpen(false);
    if (isInternalPath(notification.link)) navigate(notification.link);
  }

  return (
    <div ref={rootRef} className="relative" onBlur={onBlur}>
      <Button
        ref={buttonRef}
        type="button"
        variant="ghost"
        size="icon"
        aria-expanded={open}
        aria-controls={open ? "notifications-panel" : undefined}
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        onClick={() => setOpen((value) => !value)}
        className="relative"
      >
        <Bell aria-hidden="true" />
        {unread > 0 ? (
          <span
            aria-hidden="true"
            className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-[11px] font-semibold leading-none text-destructive-foreground shadow-sm"
          >
            {unread > 99 ? "99+" : unread}
          </span>
        ) : null}
      </Button>

      {/* Polite live region: groundwork for Phase 2 voice announcements. */}
      <p role="status" className="sr-only">
        {announcement}
      </p>

      {open ? (
        <div
          id="notifications-panel"
          role="region"
          aria-label="Notifications"
          className="animate-enter absolute right-0 z-40 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-xl"
        >
          <div className="flex items-center justify-between gap-2 border-b px-4 py-2">
            <h2 className="text-sm font-semibold">Notifications</h2>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={unread === 0 || markAll.isPending}
              onClick={() =>
                markAll.mutate(undefined, {
                  onSuccess: (result) =>
                    setAnnouncement(
                      result.updated > 0
                        ? `${result.updated} ${result.updated === 1 ? "notification" : "notifications"} marked as read.`
                        : "No unread notifications.",
                    ),
                })
              }
            >
              {markAll.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              Mark all as read
            </Button>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {isPending ? (
              <p className="p-4 text-sm text-muted-foreground" role="status">
                Loading notifications…
              </p>
            ) : null}
            {isError ? (
              <div className="space-y-2 p-4">
                <p role="alert" className="text-sm text-destructive">
                  {getErrorMessage(error)}
                </p>
                <Button variant="outline" size="sm" onClick={() => void refetch()}>
                  Try again
                </Button>
              </div>
            ) : null}
            {data && items.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">You have no notifications.</p>
            ) : null}

            {items.length > 0 ? (
              <ul className="divide-y">
                {items.map((notification) => (
                  <li key={notification.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(notification)}
                      className={cn(
                        "flex w-full items-start gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                        !notification.is_read && "bg-primary/5",
                      )}
                    >
                      <span
                        aria-hidden="true"
                        className={cn(
                          "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                          notification.is_read ? "bg-transparent" : "bg-primary",
                        )}
                      />
                      <span className="min-w-0 flex-1">
                        {!notification.is_read ? <span className="sr-only">Unread: </span> : null}
                        <span className={cn("block break-words", !notification.is_read && "font-semibold")}>
                          {notification.title}
                        </span>
                        {notification.body ? (
                          <span className="block break-words text-muted-foreground">{notification.body}</span>
                        ) : null}
                        <time dateTime={notification.created_at} className="block text-xs text-muted-foreground">
                          {formatDateTime(notification.created_at)}
                        </time>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          {markRead.isError || markAll.isError ? (
            <p role="alert" className="border-t px-4 py-2 text-xs text-destructive">
              {getErrorMessage(markRead.error ?? markAll.error)}
            </p>
          ) : null}
          {data && data.total > items.length ? (
            <p className="border-t px-4 py-2 text-xs text-muted-foreground">
              Showing the latest {items.length} of {data.total}.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

```ts
STEP 17: To-Do page, notification bell, WebSocket client
No new packages and no backend changes. Delete pages/TodoPage.tsx after creating pages/Todo.tsx, as in STEP 14.
Design decisions:
To-Do groups. The page requests /todo?limit=100 (the API maximum) and groups it in the browser. Groups are Overdue, Today, This week (the next 7 days after today), Later (including items with no due date), and a collapsed Done section. 
oOverdue means due before now, so an item due at 9am is overdue at 10am.
oThe grouping is a pure function in grouping.ts. A clock hook re-groups every minute.
oItems whose work is already turned in show as done. The server won't let you un-do them.
Notification dropdown. It is a small accessible disclosure instead of a new dependency. It shows the 10 latest notifications. 
oThe bell has an unread badge and an aria-label such as "Notifications, 3 unread".
oEscape closes the dropdown and returns focus to the bell.
oClicking an item marks it read and follows its link. Backend links like /classrooms/{id}/assignments/{id} are caught by the STEP 15 redirect.
oA polite live region announces new notifications, as groundwork for Phase 2.
WebSocket client. 
oAuth: it uses first-message auth, so the token never appears in the URL or in server logs. ?token= would also work.
oUpdates: every notification message and every connected message invalidates ['notifications']. The connected case catches anything missed while offline.
oReconnect: it reconnects with exponential backoff and jitter, and also when the browser comes back online.
oCode 4401 (the token expired; the server closes the socket at the token's exp): it refreshes the token through the same single-flight refresh as the Axios client, then reconnects. If a different request already refreshed the token, it just reconnects. Three auth failures in a row stop it.
oCode 4429 (more than 5 sockets for this user): it stops reconnecting.
oFallback: while the socket isn't open, the bell polls every 60 s.
oLifecycle: one socket per signed-in tab, closed on logout. The connection is made in AppLayout, so it survives navigation.
Files in this step
frontend/src/
├── types/index.ts                                   ← EDIT    (append block)
├── api/ws.ts                                        ← NEW
├── components/layout/
│   ├── AppLayout.tsx                                ← REPLACE (connects the socket)
│   └── TopNav.tsx                                   ← EDIT    (add the bell)
├── features/
│   ├── todo/{api,hooks,grouping}.ts                 ← NEW
│   └── notifications/
│       ├── {api,hooks,useNotificationSocket}.ts     ← NEW
│       └── components/NotificationBell.tsx          ← NEW
├── pages/Todo.tsx                                   ← NEW (replaces TodoPage.tsx)
└── routes/index.tsx                                 ← EDIT    (1 import)
cd frontend/src
rm pages/TodoPage.tsx features/todo/.gitkeep features/notifications/.gitkeep
mkdir -p features/notifications/components
touch api/ws.ts features/todo/{api,hooks,grouping}.ts \
  features/notifications/{api,hooks,useNotificationSocket}.ts \
  features/notifications/components/NotificationBell.tsx pages/Todo.tsx
Types
export type TodoRefType = "assignment" | "quiz";

export interface TodoItem {
  id: string;
  user_id: string;
  title: string;
  due_at: string | null;
  ref_type: TodoRefType | null;
  ref_id: string | null;
  /** True when marked done OR the work is already turned in. */
  is_done: boolean;
  created_at: string;
  classroom_id: string | null;
  classroom_name: string | null;
  /** App route of the assignment/quiz; null for personal items. */
  link: string | null;
  is_overdue: boolean;
}

export interface TodoList extends Page<TodoItem> {
  pending_count: number;
  overdue_count: number;
}

/** (Named `AppNotification` so it does not shadow the DOM `Notification` class.) */
export interface AppNotification {
  id: string;
  user_id: string;
  title: string;
  body: string | null;
  type: string;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export interface NotificationPage extends Page<AppNotification> {
  unread_count: number;
}
To-Do
import { api } from "@/api/client";
import type { TodoItem, TodoList } from "@/types";

export const todoApi = {
  /** Explicit items plus derived pending work. 100 is the API maximum. */
  list: () => api.get<TodoList>("/todo", { params: { limit: 100 } }).then((r) => r.data),

  /** Work that is already turned in always stays done, whatever you send. */
  mark: (id: string, isDone: boolean) =>
    api.patch<TodoItem>(`/todo/${id}`, { is_done: isDone }).then((r) => r.data),
};
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { todoApi } from "@/features/todo/api";

export const todoKeys = {
  all: ["todo"] as const,
  list: () => ["todo", "list"] as const,
};

export function useTodos() {
  return useQuery({ queryKey: todoKeys.list(), queryFn: todoApi.list });
}

export function useToggleTodo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isDone }: { id: string; isDone: boolean }) => todoApi.mark(id, isDone),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: todoKeys.all }),
  });
}
import type { TodoItem } from "@/types";

export type TodoGroupKey = "overdue" | "today" | "week" | "later" | "done";

export interface TodoGroup {
  key: TodoGroupKey;
  label: string;
  hint?: string;
  items: TodoItem[];
}

const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days); // calendar arithmetic: safe across DST changes
  return next;
}

const FAR = Number.MAX_SAFE_INTEGER;
const dueTime = (item: TodoItem) => (item.due_at ? new Date(item.due_at).getTime() : FAR);

/**
 * Split items into Overdue / Today / This week / Later / Done (in the user's local time).
 *
 * * Overdue: not done and due before `now`.
 * * Today:   due from `now` until the end of today.
 * * This week: due tomorrow through the next 6 days.
 * * Later:   due after that, or no due date.
 * * Done:    everything finished (any date).
 *
 * Every group is returned (possibly empty) in a fixed order; items are sorted by due date.
 */
export function groupTodos(items: TodoItem[], now: Date = new Date()): TodoGroup[] {
  const tomorrow = addDays(startOfDay(now), 1);
  const weekEnd = addDays(startOfDay(now), 7);

  const groups: Record<TodoGroupKey, TodoItem[]> = { overdue: [], today: [], week: [], later: [], done: [] };

  for (const item of items) {
    if (item.is_done) {
      groups.done.push(item);
    } else if (!item.due_at) {
      groups.later.push(item);
    } else {
      const due = new Date(item.due_at);
      if (due < now) groups.overdue.push(item);
      else if (due < tomorrow) groups.today.push(item);
      else if (due < weekEnd) groups.week.push(item);
      else groups.later.push(item);
    }
  }

  for (const list of Object.values(groups)) {
    list.sort((a, b) => dueTime(a) - dueTime(b) || a.title.localeCompare(b.title));
  }

  return [
    { key: "overdue", label: "Overdue", items: groups.overdue },
    { key: "today", label: "Today", items: groups.today },
    { key: "week", label: "This week", hint: "Next 7 days", items: groups.week },
    { key: "later", label: "Later", hint: "Including items with no due date", items: groups.later },
    { key: "done", label: "Done", items: groups.done },
  ];
}
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { AsyncList } from "@/components/common/AsyncList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { groupTodos, type TodoGroup } from "@/features/todo/grouping";
import { useToggleTodo, useTodos } from "@/features/todo/hooks";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { formatDateTime } from "@/lib/format";
import type { TodoItem } from "@/types";

/** Current time, refreshed every minute so items move to "Overdue" while the page is open. */
function useNow(intervalMs = 60_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

function TodoRow({
  item,
  overdue,
  pending,
  onToggle,
}: {
  item: TodoItem;
  overdue: boolean;
  pending: boolean;
  onToggle: (isDone: boolean) => void;
}) {
  const kind = item.ref_type === "quiz" ? "Quiz" : item.ref_type === "assignment" ? "Assignment" : "Personal";
  const checkboxId = `todo-${item.id}`;
  return (
    <li className="flex items-start gap-3 py-3">
      <input
        id={checkboxId}
        type="checkbox"
        className="mt-1 h-4 w-4 shrink-0 accent-primary"
        checked={item.is_done}
        disabled={pending}
        onChange={(e) => onToggle(e.target.checked)}
        aria-label={`Mark “${item.title}” as ${item.is_done ? "not done" : "done"}`}
      />
      <div className="min-w-0 flex-1">
        <p className={item.is_done ? "break-words text-muted-foreground line-through" : "break-words font-medium"}>
          {item.link ? (
            <Link
              to={item.link}
              className="underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {item.title}
            </Link>
          ) : (
            item.title
          )}
        </p>
        <p className="text-sm text-muted-foreground">
          {kind}
          {item.classroom_name ? ` · ${item.classroom_name}` : ""}
          {item.due_at ? (
            <>
              {" · due "}
              <time dateTime={item.due_at}>{formatDateTime(item.due_at)}</time>
            </>
          ) : (
            " · no due date"
          )}
        </p>
      </div>
      {overdue ? <Badge variant="destructive">Overdue</Badge> : null}
    </li>
  );
}

function GroupSection({
  group,
  pendingId,
  onToggle,
}: {
  group: TodoGroup;
  pendingId: string | null;
  onToggle: (item: TodoItem, isDone: boolean) => void;
}) {
  const headingId = `todo-group-${group.key}`;
  const rows = (
    <ul className="divide-y rounded-lg border px-4">
      {group.items.map((item) => (
        <TodoRow
          key={item.id}
          item={item}
          overdue={group.key === "overdue"}
          pending={pendingId === item.id}
          onToggle={(isDone) => onToggle(item, isDone)}
        />
      ))}
    </ul>
  );

  const title = (
    <>
      {group.label} <span className="text-sm font-normal text-muted-foreground">({group.items.length})</span>
      {group.hint ? <span className="ml-2 text-xs font-normal text-muted-foreground">{group.hint}</span> : null}
    </>
  );

  // "Done" is collapsed by default: a native <details> is keyboard and screen-reader friendly.
  if (group.key === "done") {
    return (
      <details className="group">
        <summary className="cursor-pointer text-lg font-semibold">{title}</summary>
        <div className="mt-3">{rows}</div>
      </details>
    );
  }
  return (
    <section aria-labelledby={headingId} className="space-y-3">
      <h2 id={headingId} className={group.key === "overdue" ? "text-lg font-semibold text-destructive" : "text-lg font-semibold"}>
        {title}
      </h2>
      {rows}
    </section>
  );
}

export function TodoPage() {
  useDocumentTitle("To-Do");
  const { data, isPending, error, refetch } = useTodos();
  const toggle = useToggleTodo();
  const now = useNow();

  const groups = useMemo(() => (data ? groupTodos(data.items, now) : []), [data, now]);
  const pendingId = toggle.isPending ? (toggle.variables?.id ?? null) : null;

  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-3xl space-y-6">
      <div className="space-y-1">
        <h1 id="page-title" className="text-2xl font-semibold tracking-tight">To-Do</h1>
        {data ? (
          <p className="text-muted-foreground">
            {data.pending_count} to do
            {data.overdue_count > 0 ? <span className="text-destructive"> · {data.overdue_count} overdue</span> : null}
          </p>
        ) : null}
      </div>

      <ErrorAlert message={toggle.isError ? getErrorMessage(toggle.error) : null} />

      <AsyncList
        isPending={isPending}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={data?.items.length === 0}
        emptyText="Nothing to do. Published assignments and quizzes from your classes will appear here."
        loadingLabel="Loading your to-do list…"
      >
        <div className="space-y-8">
          {groups
            .filter((group) => group.items.length > 0)
            .map((group) => (
              <GroupSection
                key={group.key}
                group={group}
                pendingId={pendingId}
                onToggle={(item, isDone) => toggle.mutate({ id: item.id, isDone })}
              />
            ))}
          {data && data.total > data.items.length ? (
            <p className="text-xs text-muted-foreground">Showing the first {data.items.length} of {data.total} items.</p>
          ) : null}
        </div>
      </AsyncList>
    </section>
  );
}
// REPLACE
import { TodoPage } from "@/pages/TodoPage";
// WITH
import { TodoPage } from "@/pages/Todo";
Notifications
import { api } from "@/api/client";
import type { AppNotification, NotificationPage } from "@/types";

export const notificationsApi = {
  /** Newest first. `unread_count` covers ALL notifications, not just this page. */
  list: (limit: number) =>
    api.get<NotificationPage>("/notifications", { params: { limit } }).then((r) => r.data),

  /** Idempotent. */
  markRead: (id: string) =>
    api.patch<AppNotification>(`/notifications/${id}/read`).then((r) => r.data),

  markAllRead: () => api.post<{ updated: number }>("/notifications/read-all").then((r) => r.data),
};
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
import { create } from "zustand";

import { refreshAccessToken } from "@/api/client";
import { env } from "@/lib/env";
import { queryClient } from "@/lib/queryClient";
import { useAuthStore } from "@/store/auth";

export type SocketStatus = "idle" | "connecting" | "open" | "closed";

/** Connection state, so the UI can fall back to polling while the socket is down. */
export const useSocketStatus = create<{ status: SocketStatus }>(() => ({ status: "idle" }));
const setStatus = (status: SocketStatus) => useSocketStatus.setState({ status });

// Close codes defined by the backend (WS /ws/notifications).
const CLOSE_UNAUTHORIZED = 4401; // bad/expired token (also sent when the token reaches `exp`)
const CLOSE_TOO_MANY = 4429; // more than 5 sockets for this user: do not retry

const PING_INTERVAL_MS = 30_000; // the server closes sockets that are idle for 90 s
const MAX_BACKOFF_MS = 30_000;
const MAX_AUTH_FAILURES = 3;

function invalidateNotifications(): void {
  void queryClient.invalidateQueries({ queryKey: ["notifications"] });
}

/**
 * Opens the notifications socket and keeps it alive. Returns a function that stops it.
 *
 * The access token is sent as the FIRST MESSAGE (`{"type":"auth","token":...}`), not in the
 * URL, so it never ends up in access logs.
 */
export function connectNotifications(): () => void {
  let socket: WebSocket | null = null;
  let stopped = false;
  let attempts = 0;
  let authFailures = 0;
  let tokenUsed: string | null = null;
  let retryTimer: number | undefined;
  let pingTimer: number | undefined;

  const clearTimers = () => {
    window.clearTimeout(retryTimer);
    window.clearInterval(pingTimer);
    retryTimer = undefined;
    pingTimer = undefined;
  };

  function scheduleReconnect(): void {
    if (stopped) return;
    const delay = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** attempts) + Math.random() * 500;
    attempts += 1;
    window.clearTimeout(retryTimer);
    retryTimer = window.setTimeout(open, delay);
  }

  /** Server closed with 4401: refresh the token if nobody did yet, then reconnect. */
  async function recoverFromAuthFailure(): Promise<void> {
    authFailures += 1;
    if (authFailures >= MAX_AUTH_FAILURES) return; // something is wrong with the session: stop
    try {
      if (useAuthStore.getState().accessToken === tokenUsed) await refreshAccessToken();
    } catch {
      // A rejected refresh token already cleared the session (the router sends the user to
      // /login and this socket is stopped). A network error just retries with backoff.
      scheduleReconnect();
      return;
    }
    if (!stopped) open();
  }

  function open(): void {
    if (stopped) return;
    const token = useAuthStore.getState().accessToken;
    if (!token) {
      setStatus("closed");
      return;
    }
    tokenUsed = token;
    setStatus("connecting");

    const ws = new WebSocket(`${env.WS_URL}/ws/notifications`);
    socket = ws;

    ws.onopen = () => ws.send(JSON.stringify({ type: "auth", token }));

    ws.onmessage = (event: MessageEvent<string>) => {
      let message: { type?: string } | null = null;
      try {
        message = JSON.parse(event.data) as { type?: string };
      } catch {
        return;
      }
      if (message.type === "connected") {
        attempts = 0;
        authFailures = 0;
        setStatus("open");
        window.clearInterval(pingTimer);
        pingTimer = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
        }, PING_INTERVAL_MS);
        invalidateNotifications(); // catch up on anything missed while disconnected
      } else if (message.type === "notification") {
        invalidateNotifications();
      }
    };

    ws.onerror = () => {
      /* a close event always follows; handled there */
    };

    ws.onclose = (event: CloseEvent) => {
      if (socket !== ws) return; // an old socket, or we were stopped
      socket = null;
      window.clearInterval(pingTimer);
      setStatus("closed");
      if (stopped) return;

      if (event.code === CLOSE_TOO_MANY) return;
      if (event.code === CLOSE_UNAUTHORIZED) {
        void recoverFromAuthFailure();
        return;
      }
      scheduleReconnect();
    };
  }

  const onOnline = () => {
    if (stopped || socket) return;
    attempts = 0;
    window.clearTimeout(retryTimer);
    open();
  };
  window.addEventListener("online", onOnline);

  open();

  return () => {
    stopped = true;
    clearTimers();
    window.removeEventListener("online", onOnline);
    const current = socket;
    socket = null; // makes its onclose handler a no-op
    current?.close(1000);
    setStatus("idle");
  };
}
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
import { Bell } from "lucide-react";
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
function isInternalPath(link: string | null): link is string {
  return Boolean(link) && (link as string).startsWith("/") && !(link as string).startsWith("//");
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
        aria-controls="notifications-panel"
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        onClick={() => setOpen((value) => !value)}
        className="relative"
      >
        <Bell aria-hidden="true" />
        {unread > 0 ? (
          <span
            aria-hidden="true"
            className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-[11px] font-semibold leading-none text-destructive-foreground"
          >
            {unread > 99 ? "99+" : unread}
          </span>
        ) : null}
      </Button>

      <p role="status" className="sr-only">{announcement}</p>

      {open ? (
        <div
          id="notifications-panel"
          role="region"
          aria-label="Notifications"
          className="absolute right-0 z-40 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] rounded-lg border bg-popover text-popover-foreground shadow-lg"
        >
          <div className="flex items-center justify-between gap-2 border-b px-4 py-2">
            <h2 className="text-sm font-semibold">Notifications</h2>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={unread === 0 || markAll.isPending}
              onClick={() => markAll.mutate()}
            >
              Mark all as read
            </Button>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {isPending ? <p className="p-4 text-sm text-muted-foreground">Loading…</p> : null}
            {isError ? (
              <div className="space-y-2 p-4">
                <p role="alert" className="text-sm text-destructive">{getErrorMessage(error)}</p>
                <Button variant="outline" size="sm" onClick={() => void refetch()}>Try again</Button>
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
                        className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", notification.is_read ? "bg-transparent" : "bg-primary")}
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
            <p className="border-t px-4 py-2 text-xs text-muted-foreground">Showing the latest {items.length} of {data.total}.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
Layout wiring
import { Outlet } from "react-router-dom";

import { TopNav } from "@/components/layout/TopNav";
import { useNotificationSocket } from "@/features/notifications/useNotificationSocket";

export function AppLayout() {
  useNotificationSocket(); // one live notifications socket per signed-in tab

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to main content
      </a>
      <TopNav />
      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-6xl px-4 py-6 focus:outline-none">
        <Outlet />
      </main>
    </div>
  );
}
// 1) add to the imports:
import { NotificationBell } from "@/features/notifications/components/NotificationBell";

// 2) in the right-hand div (className="ml-auto flex items-center gap-3"),
//    add the bell as the FIRST child, before the user's name:
        <div className="ml-auto flex items-center gap-3">
          <NotificationBell />
          {user ? (
            ...

How to run and test
# backend (keep ONE uvicorn worker: the socket registry is in-process)
cd backend && uvicorn app.main:app --reload --port 8000

cd frontend
npm run build      # type-checks
npm run dev
Checklist
Use two browser profiles: teacher Tina and student Sam (Sam is in Tina's class).
To-Do (as Sam)
#	Do this	Expected
1	Tina publishes assignments due in the past, later today, in 3 days, in 20 days, and with no due date, plus a quiz	Sam's To-Do shows groups Overdue (red), Today, This week, Later (20 days and no due date). Empty groups are hidden
2	Look at the header	"N to do · M overdue"
3	Tick an item	It moves to Done (collapsed). The counters update
4	Expand Done with the keyboard (Enter on the summary)	The list opens
5	Click an item title	Opens the assignment or quiz page (through the /classrooms/... redirect)
6	Turn in an assignment, then return to To-Do	That item is in Done. Unticking it leaves it done
7	Leave the page open past a due time	Within a minute the item moves to Overdue
8	Stop the API and reload	Error with Try again
Notifications and WebSocket
#	Do this	Expected
9	Sign in as Sam, open DevTools → Network → WS	One /ws/notifications connection. First frame sent is {"type":"auth",...}, then you receive {"type":"connected","unread_count":n}. A ping goes out every 30 s
10	As Tina, add a material	Within a second Sam's bell shows a red badge, with no refresh. The status line announces "New notification: New material: …"
11	Click the bell	Panel with the latest notifications; unread ones are bold with a dot
12	Click a notification	It is marked read (badge drops), the panel closes, and the linked page opens
13	Mark all as read	Badge disappears and the button disables
14	Press Esc with the panel open	It closes and focus returns to the bell
15	Click outside the panel, or Tab out of it	It closes
16	Sam turns in work, and Tina has the bell open	Tina gets "Sam turned in …" live
17	Tina returns work	Sam gets "Your work on … was returned"
18	Stop the API for 10 s, then start it	Status drops, then the client reconnects by itself (backoff 1 s, 2 s, 4 s…). A connected frame arrives and the notification list refreshes
19	Set ACCESS_TOKEN_EXPIRE_MINUTES=1, restart the API, sign in, wait about 60 s	The socket closes with code 4401, one POST /auth/refresh runs, and a new socket connects. No visible glitch
20	Open 6 tabs as the same user	The 6th socket closes with 4429 and does not retry. That tab falls back to polling every 60 s
21	Click Log out	The socket closes (code 1000) and the bell disappears
Troubleshooting
Problem	Fix
No live updates, WS status "closed" in the console	Check VITE_WS_URL (ws://localhost:8000, no path). Behind a proxy, /ws/ needs the Upgrade headers
The socket connects, then closes with 4401 immediately	The access token is expired or invalid. The client refreshes once and retries. After 3 failures in a row it stops, so sign in again
Bell badge only updates after about a minute	The socket is down, so the bell is polling. Check the Network → WS tab
Two sockets in dev	React StrictMode mounts effects twice. The first socket is closed straight away. Production builds open one
Notification click goes nowhere	The notification has no link, or it does not start with /. It is only marked read
Cannot find module '@/pages/Todo'	The file name must be Todo.tsx, and routes/index.tsx must use the new import
Same notification twice	Not possible: the cache is invalidated and refetched, never appended
Reply NEXT for STEP 18.
```
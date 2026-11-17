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
 * `env.WS_URL` already includes the `/ws` prefix (see `.env`), so the path is `/notifications`.
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

    const ws = new WebSocket(`${env.WS_URL}/notifications`);
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

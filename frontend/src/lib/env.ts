const trimSlash = (value: string) => value.replace(/\/+$/, "");

export const env = {
  /** REST base URL, including /api/v1 */
  API_URL: trimSlash(import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1"),
  /** WebSocket base URL (the notifications socket is `${WS_URL}/ws/notifications`) */
  WS_URL: trimSlash(import.meta.env.VITE_WS_URL ?? "ws://localhost:8000"),
} as const;

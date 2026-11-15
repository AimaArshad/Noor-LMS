const trimSlash = (value: string) => value.replace(/\/+$/, "");

/**
 * Environment values are configuration, never code: nothing here falls back to a hard-coded
 * URL. A missing variable fails loudly at startup instead of silently pointing at the wrong
 * backend (or at production from a local build).
 */
function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Missing ${name}. Copy frontend/.env.example to frontend/.env and restart the dev server.`);
  }
  return trimSlash(value);
}

export const env = {
  /** REST base URL, including /api/v1 (VITE_API_BASE_URL). */
  API_URL: required("VITE_API_BASE_URL", import.meta.env.VITE_API_BASE_URL),
  /** WebSocket base URL, including the /ws prefix (VITE_WS_URL). */
  WS_URL: required("VITE_WS_URL", import.meta.env.VITE_WS_URL),
} as const;

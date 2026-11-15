/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** REST base URL, including the /api/v1 prefix. */
  readonly VITE_API_BASE_URL: string;
  /** WebSocket base URL, including the /ws prefix. */
  readonly VITE_WS_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

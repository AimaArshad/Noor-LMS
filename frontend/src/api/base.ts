import axios from "axios";

import { env } from "@/lib/env";

/**
 * Bare axios instance WITHOUT interceptors. Used for the auth endpoints and by the auth
 * store, so the store never imports `client.ts` (which imports the store).
 */
export const authHttp = axios.create({
  baseURL: env.API_URL,
  timeout: 30_000,
  headers: { Accept: "application/json" },
});

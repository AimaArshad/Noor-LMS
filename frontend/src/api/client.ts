import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

import { authApi } from "@/api/auth";
import { getStatus } from "@/api/errors";
import { env } from "@/lib/env";
import { useAuthStore } from "@/store/auth";

/** Axios instance for every authenticated API call. */
export const api = axios.create({
  baseURL: env.API_URL,
  timeout: 30_000,
  headers: { Accept: "application/json" },
});

// ---------------------------------------------------------------------- request
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ------------------------------------------------------------- refresh-on-401
let inflight: Promise<string> | null = null;

/**
 * Exchange the refresh token for a new pair and return the new access token.
 *
 * Single-flight: while one refresh is running, every caller gets the same promise. This
 * matters because the backend ROTATES refresh tokens (the old one is revoked on use), so
 * two parallel refreshes would make the second one fail and log the user out.
 */
export function refreshAccessToken(): Promise<string> {
  if (inflight) return inflight;

  const { refreshToken } = useAuthStore.getState();
  if (!refreshToken) return Promise.reject(new Error("No refresh token"));

  inflight = authApi
    .refresh(refreshToken)
    .then((pair) => {
      useAuthStore.getState().setTokens(pair.access_token, pair.refresh_token);
      return pair.access_token;
    })
    .catch((error: unknown) => {
      // Only a definite rejection ends the session; a network blip or a 503 (Redis down) keeps it.
      if (getStatus(error) === 401) useAuthStore.getState().clearSession();
      throw error;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean };

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;
    const isUnauthorized = error.response?.status === 401;

    // Not a 401, already retried once, or the user has no session: surface the error as is.
    if (!original || !isUnauthorized || original._retry || !useAuthStore.getState().refreshToken) {
      return Promise.reject(error);
    }

    original._retry = true;
    try {
      const token = await refreshAccessToken();
      original.headers.Authorization = `Bearer ${token}`;
      return api(original);
    } catch {
      return Promise.reject(error); // the original 401; the store has already cleared a dead session
    }
  },
);

export { axios };

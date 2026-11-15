import { create } from "zustand";

import { authApi } from "@/api/auth";
import { getStatus } from "@/api/errors";
import { queryClient } from "@/lib/queryClient";
import type { LoginInput, User } from "@/types";

const STORAGE_KEY = "noorlms.auth.v1";

interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

// NOTE: tokens in localStorage are readable by any script on the page (XSS). Keep the app free
// of dangerouslySetInnerHTML and third-party scripts; an httpOnly-cookie refresh flow would be
// the hardening step if this ever needs to be stricter.
function readTokens(): StoredTokens | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredTokens>;
    if (typeof parsed.accessToken === "string" && typeof parsed.refreshToken === "string") {
      return { accessToken: parsed.accessToken, refreshToken: parsed.refreshToken };
    }
  } catch {
    /* corrupt or unavailable storage: treat as logged out */
  }
  return null;
}

function writeTokens(tokens: StoredTokens | null): void {
  try {
    if (tokens) localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage full / blocked: the session simply will not survive a reload */
  }
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  /** False until `hydrate()` has finished; route guards wait for it. */
  hydrated: boolean;

  login: (credentials: LoginInput) => Promise<User>;
  logout: () => Promise<void>;
  hydrate: () => Promise<void>;

  /** Used by the Axios refresh interceptor. */
  setTokens: (accessToken: string, refreshToken: string) => void;
  /** Local-only logout: wipe state, storage and the query cache. */
  clearSession: () => void;
}

let hydrating: Promise<void> | null = null;

export const useAuthStore = create<AuthState>()((set, get) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  hydrated: false,

  async login(credentials) {
    const pair = await authApi.login(credentials);
    const user = await authApi.me(pair.access_token); // nothing is stored if this fails
    writeTokens({ accessToken: pair.access_token, refreshToken: pair.refresh_token });
    queryClient.clear(); // never show the previous user's cached data
    set({
      user,
      accessToken: pair.access_token,
      refreshToken: pair.refresh_token,
      hydrated: true,
    });
    return user;
  },

  async logout() {
    const { refreshToken } = get();
    get().clearSession(); // sign out locally first: the UI must not wait for the network
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken); // revokes the refresh token server-side
      } catch {
        /* best effort: the token also expires on its own */
      }
    }
  },

  hydrate() {
    if (get().hydrated) return Promise.resolve();
    hydrating ??= (async () => {
      const stored = readTokens();
      if (!stored) {
        set({ hydrated: true });
        return;
      }
      try {
        let { accessToken, refreshToken } = stored;
        let user: User;
        try {
          user = await authApi.me(accessToken);
        } catch (error) {
          if (getStatus(error) !== 401) throw error;
          // Access token expired: rotate once, persist the new pair at once, retry.
          const pair = await authApi.refresh(refreshToken);
          accessToken = pair.access_token;
          refreshToken = pair.refresh_token;
          writeTokens({ accessToken, refreshToken });
          user = await authApi.me(accessToken);
        }
        set({ user, accessToken, refreshToken, hydrated: true });
      } catch (error) {
        // A rejected session is wiped. After a network error the tokens stay stored, so the
        // next reload can still restore the session.
        if (getStatus(error) === 401) writeTokens(null);
        set({ user: null, accessToken: null, refreshToken: null, hydrated: true });
      }
    })().finally(() => {
      hydrating = null;
    });
    return hydrating;
  },

  setTokens(accessToken, refreshToken) {
    writeTokens({ accessToken, refreshToken });
    set({ accessToken, refreshToken });
  },

  clearSession() {
    writeTokens(null);
    set({ user: null, accessToken: null, refreshToken: null });
    queryClient.clear();
  },
}));

// Keep several tabs consistent. The `storage` event fires only in the OTHER tabs.
if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    if (event.key !== null && event.key !== STORAGE_KEY) return;
    const stored = readTokens();
    const state = useAuthStore.getState();

    if (!stored) {
      // logged out in another tab
      useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });
      queryClient.clear();
      return;
    }
    // tokens were rotated or a login happened in another tab
    useAuthStore.setState({ accessToken: stored.accessToken, refreshToken: stored.refreshToken });
    if (!state.user) {
      useAuthStore.setState({ hydrated: false });
      void useAuthStore.getState().hydrate();
    }
  });
}

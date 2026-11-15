```ts STEP 13: Frontend scaffold
// Everything here is ready to paste. Three choices were made on purpose:
Tailwind 3.4, not 4. shadcn/ui’s stable path for Tailwind 3 is the one I can give you complete and reliable files for. The components are written by hand, and components.json is included so npx shadcn@2.3.0 add <component> works later.
The auth store never imports the Axios client. store/auth.ts talks to the backend through a bare Axios instance (api/base.ts), and api/client.ts imports the store. That avoids a circular import.
Refresh tokens rotate on the backend, so the frontend must never refresh twice at once. 
oConcurrent 401s share one in-flight refresh call.
ohydrate() is guarded against React StrictMode’s double effect.
oA storage listener keeps other browser tabs in sync.
Accessibility groundwork for Phase 2 is already in: skip link, landmarks, aria-current on nav, role="alert" errors and a document title per page.
Folder tree and setup
Do not run npm create vite. The files below replace its output (it now generates React 19, and this project targets 18).
text
educonnect/
├── docker-compose.yml              ← EDIT (add frontend service)
└── frontend/
    ├── .dockerignore
    ├── .env.example
    ├── .gitignore
    ├── Dockerfile
    ├── nginx.conf
    ├── components.json
    ├── index.html
    ├── package.json
    ├── postcss.config.js
    ├── tailwind.config.ts
    ├── tsconfig.json
    ├── tsconfig.app.json
    ├── tsconfig.node.json
    ├── vite.config.ts
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── index.css
        ├── vite-env.d.ts
        ├── api/
        │   ├── base.ts             # bare axios (no interceptors)
        │   ├── client.ts           # axios + token attach + refresh-on-401
        │   ├── auth.ts
        │   └── errors.ts
        ├── components/
        │   ├── ui/                 # shadcn: button, input, label, card
        │   ├── common/             # Spinner, PagePlaceholder
        │   └── layout/             # AppLayout, TopNav, ClassroomLayout, ClassroomSidebar, AuthShell
        ├── features/
        │   ├── classrooms/         # api.ts, hooks.ts, context.ts
        │   └── {assignments,quizzes,materials,announcements,todo,notifications,files}/.gitkeep
        ├── hooks/useDocumentTitle.ts
        ├── lib/                    # env.ts, utils.ts, queryClient.ts
        ├── pages/                  # auth/, classroom/, Home, Todo, Classes, Profile, Admin, NotFound, Forbidden
        ├── routes/                 # index.tsx, ProtectedRoute, RoleRoute, GuestRoute
        ├── store/auth.ts
        └── types/index.ts
bash
# from the repo root
mkdir -p frontend && cd frontend
mkdir -p src/{api,hooks,lib,routes,store,types} \
         src/components/{ui,common,layout} \
         src/pages/{auth,classroom} \
         src/features/classrooms
for f in assignments quizzes materials announcements todo notifications files; do
  mkdir -p src/features/$f && touch src/features/$f/.gitkeep
done
npm install list
Create package.json (below), then run npm install. The equivalent manual commands are:
bash
# runtime
npm install react@18 react-dom@18 react-router-dom@6 @tanstack/react-query axios zustand \
  clsx tailwind-merge class-variance-authority lucide-react tailwindcss-animate \
  @radix-ui/react-slot @radix-ui/react-label

# dev
npm install -D vite @vitejs/plugin-react typescript@~5.6 tailwindcss@3 postcss autoprefixer \
  @types/node @types/react@18 @types/react-dom@18
The versions in package.json are the ones I know; run npm outdated afterwards to see newer patch releases.
Config files
json
{
  "name": "educonnect-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "typecheck": "tsc -b"
  },
  "dependencies": {
    "@radix-ui/react-label": "^2.1.0",
    "@radix-ui/react-slot": "^1.1.0",
    "@tanstack/react-query": "^5.62.0",
    "axios": "^1.7.9",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.468.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "tailwind-merge": "^2.5.5",
    "tailwindcss-animate": "^1.0.7",
    "zustand": "^5.0.2"
  },
  "devDependencies": {
    "@types/node": "^22.10.0",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "typescript": "~5.6.3",
    "vite": "^6.0.3"
  }
}
text
# Base URL of the REST API INCLUDING the /api/v1 prefix
VITE_API_URL=http://localhost:8000/api/v1
# Base URL of the WebSocket server (no path; the app appends /ws/notifications)
VITE_WS_URL=ws://localhost:8000
text
node_modules
dist
.env
.env.local
*.local
*.tsbuildinfo
text
node_modules
dist
.env
.git
html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="EduConnect: classes, assignments and quizzes in one place." />
    <title>EduConnect</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
ts
import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // 5173 is the origin the backend's CORS_ORIGINS allows by default.
  server: { host: true, port: 5173, strictPort: true },
  preview: { port: 5173 },
});
json
{
  "files": [],
  "references": [{ "path": "./tsconfig.app.json" }, { "path": "./tsconfig.node.json" }],
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"]
}
json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "strict": true,
    "types": ["node"]
  },
  "include": ["vite.config.ts", "tailwind.config.ts"]
}
js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
ts
import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        popover: { DEFAULT: "hsl(var(--popover))", foreground: "hsl(var(--popover-foreground))" },
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [animate],
};

export default config;
json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/index.css",
    "baseColor": "slate",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
dockerfile
# Targets: `dev` (Vite dev server, used by docker-compose) and `prod` (static build behind nginx).
# Requires package-lock.json (created by your first `npm install`).
FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

FROM base AS dev
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM base AS build
# Vite inlines VITE_* values at BUILD time.
ARG VITE_API_URL
ARG VITE_WS_URL
ENV VITE_API_URL=$VITE_API_URL VITE_WS_URL=$VITE_WS_URL
RUN npm run build

FROM nginx:1.27-alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;

  # Hashed build assets: cache for a year
  location /assets/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    try_files $uri =404;
  }

  # Single-page app: every other path serves index.html (React Router handles it)
  location / {
    add_header Cache-Control "no-cache";
    try_files $uri /index.html;
  }
}
yaml
  frontend:
    build:
      context: ./frontend
      target: dev
    container_name: educonnect-frontend
    environment:
      # These are used by the BROWSER, so they point at the host-published backend port.
      VITE_API_URL: http://localhost:8000/api/v1
      VITE_WS_URL: ws://localhost:8000
      CHOKIDAR_USEPOLLING: "true"      # file watching inside Docker on Windows/macOS
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules              # keep the container's node_modules
    depends_on:
      - backend
Source: entry, styles, lib
tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/App";
import "@/index.css";
import { useAuthStore } from "@/store/auth";

// Restore the session from localStorage. hydrate() is idempotent and shares one promise,
// so StrictMode / double calls can never trigger two refresh-token rotations.
void useAuthStore.getState().hydrate();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
tsx
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

import { queryClient } from "@/lib/queryClient";
import { router } from "@/routes";

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 40%; /* darker than the shadcn default: WCAG AA on white */
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 72% 45%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 85%;
    --ring: 221.2 83.2% 53.3%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --popover: 222.2 84% 4.9%;
    --popover-foreground: 210 40% 98%;
    --primary: 217.2 91.2% 59.8%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 70%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 50%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 22%;
    --ring: 224.3 76.3% 60%;
  }

  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground antialiased;
  }
}
ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_WS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
ts
const trimSlash = (value: string) => value.replace(/\/+$/, "");

export const env = {
  /** REST base URL, including /api/v1 */
  API_URL: trimSlash(import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1"),
  /** WebSocket base URL (the notifications socket is `${WS_URL}/ws/notifications`) */
  WS_URL: trimSlash(import.meta.env.VITE_WS_URL ?? "ws://localhost:8000"),
} as const;
ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge class names; later Tailwind classes win over earlier ones. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
ts
import { QueryClient } from "@tanstack/react-query";

import { getStatus } from "@/api/errors";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // Never retry 4xx answers (404, 403, ...); retry network errors / 5xx twice.
      retry: (failureCount, error) => {
        const status = getStatus(error);
        if (status !== undefined && status < 500) return false;
        return failureCount < 2;
      },
    },
  },
});
Source: types and API layer
ts
// Mirrors the backend Pydantic schemas (STEP 4+).

export type UserRole = "teacher" | "student" | "admin";
export type MemberRole = "teacher" | "student";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  /** Access-token lifetime in seconds */
  expires_in: number;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput {
  email: string;
  password: string;
  full_name: string;
  role: Exclude<UserRole, "admin">;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/** `ClassroomDetail` from the API. `join_code` is only present for classroom teachers. */
export interface Classroom {
  id: string;
  name: string;
  section: string | null;
  subject: string | null;
  room: string | null;
  owner_id: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  my_role: MemberRole;
  join_code: string | null;
}
ts
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
ts
import axios from "axios";

/** HTTP status of a failed request, or `undefined` for network errors / non-HTTP errors. */
export function getStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

interface ValidationIssue {
  loc?: unknown[];
  msg?: string;
}

/** Turn any error (FastAPI `detail` string, 422 issue list, network failure) into UI text. */
export function getErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return "Cannot reach the server. Check your connection.";
    if (error.response.status === 429) return "Too many requests. Please wait a moment and retry.";

    const detail = (error.response.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = (detail as ValidationIssue[])
        .map((issue) => {
          const field = issue.loc?.slice(1).join(".");
          return field ? `${field}: ${issue.msg ?? "invalid"}` : (issue.msg ?? "invalid");
        })
        .filter(Boolean);
      if (messages.length) return messages.join("; ");
    }
    return fallback;
  }
  return error instanceof Error ? error.message : fallback;
}
ts
import { authHttp } from "@/api/base";
import type { LoginInput, RegisterInput, TokenPair, User } from "@/types";

export const authApi = {
  login: (body: LoginInput) =>
    authHttp.post<TokenPair>("/auth/login", body).then((r) => r.data),

  register: (body: RegisterInput) =>
    authHttp.post<User>("/auth/register", body).then((r) => r.data),

  /** Rotates tokens: the submitted refresh token can never be used again. */
  refresh: (refreshToken: string) =>
    authHttp.post<TokenPair>("/auth/refresh", { refresh_token: refreshToken }).then((r) => r.data),

  logout: (refreshToken: string) =>
    authHttp.post("/auth/logout", { refresh_token: refreshToken }).then(() => undefined),

  /** Takes the token explicitly so it can be used before the store holds it. */
  me: (accessToken: string) =>
    authHttp
      .get<User>("/auth/me", { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((r) => r.data),
};
ts
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
Source: auth store
ts
import { create } from "zustand";

import { authApi } from "@/api/auth";
import { getStatus } from "@/api/errors";
import { queryClient } from "@/lib/queryClient";
import type { LoginInput, User } from "@/types";

const STORAGE_KEY = "educonnect.auth.v1";

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
Source: route guards and router
tsx
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Spinner } from "@/components/common/Spinner";
import { useAuthStore } from "@/store/auth";

/** Renders its child routes only for a signed-in user. */
export function ProtectedRoute() {
  const hydrated = useAuthStore((s) => s.hydrated);
  const user = useAuthStore((s) => s.user);
  const location = useLocation();

  if (!hydrated) return <Spinner fullPage label="Loading your account…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}
tsx
import { Navigate, Outlet } from "react-router-dom";

import { ForbiddenPage } from "@/pages/ForbiddenPage";
import { useAuthStore } from "@/store/auth";
import type { UserRole } from "@/types";

interface RoleRouteProps {
  /** Global platform roles allowed to see the child routes. */
  roles: UserRole[];
}

/**
 * Restricts child routes to some global roles. Nest it INSIDE `ProtectedRoute`.
 * This is a UX guard only; the API enforces the real permissions.
 */
export function RoleRoute({ roles }: RoleRouteProps) {
  const user = useAuthStore((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  return roles.includes(user.role) ? <Outlet /> : <ForbiddenPage />;
}
tsx
import { Navigate, Outlet, useLocation, type Location } from "react-router-dom";

import { Spinner } from "@/components/common/Spinner";
import { useAuthStore } from "@/store/auth";

/** Login / register pages: signed-in users are sent back to where they came from. */
export function GuestRoute() {
  const hydrated = useAuthStore((s) => s.hydrated);
  const user = useAuthStore((s) => s.user);
  const location = useLocation();

  if (!hydrated) return <Spinner fullPage label="Loading…" />;
  if (user) {
    const from = (location.state as { from?: Location } | null)?.from;
    const target = from ? `${from.pathname}${from.search}${from.hash}` : "/";
    return <Navigate to={target} replace />;
  }
  return <Outlet />;
}
tsx
import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { ClassroomLayout } from "@/components/layout/ClassroomLayout";
import { AdminPage } from "@/pages/AdminPage";
import { LoginPage } from "@/pages/auth/LoginPage";
import { RegisterPage } from "@/pages/auth/RegisterPage";
import { ClassworkPage } from "@/pages/classroom/ClassworkPage";
import { PeoplePage } from "@/pages/classroom/PeoplePage";
import { StreamPage } from "@/pages/classroom/StreamPage";
import { ClassesPage } from "@/pages/ClassesPage";
import { HomePage } from "@/pages/HomePage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { TodoPage } from "@/pages/TodoPage";
import { GuestRoute } from "@/routes/GuestRoute";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { RoleRoute } from "@/routes/RoleRoute";

export const router = createBrowserRouter([
  {
    element: <GuestRoute />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "todo", element: <TodoPage /> },
          { path: "classes", element: <ClassesPage /> },
          { path: "profile", element: <ProfilePage /> },
          {
            element: <RoleRoute roles={["admin"]} />,
            children: [{ path: "admin", element: <AdminPage /> }],
          },
          {
            path: "classes/:classroomId",
            element: <ClassroomLayout />,
            children: [
              { index: true, element: <StreamPage /> },
              { path: "classwork", element: <ClassworkPage /> },
              { path: "people", element: <PeoplePage /> },
              // later steps: classwork/assignments/:id, classwork/quizzes/:id, materials/:id ...
            ],
          },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
]);
Source: shadcn/ui components
tsx
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
tsx
import * as React from "react";

import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      ref={ref}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
tsx
import * as LabelPrimitive from "@radix-ui/react-label";
import * as React from "react";

import { cn } from "@/lib/utils";

const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn(
      "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
      className,
    )}
    {...props}
  />
));
Label.displayName = LabelPrimitive.Root.displayName;

export { Label };
tsx
import * as React from "react";

import { cn } from "@/lib/utils";

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("rounded-lg border bg-card text-card-foreground shadow-sm", className)}
      {...props}
    />
  ),
);
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
  ),
);
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("text-xl font-semibold leading-none tracking-tight", className)} {...props} />
  ),
);
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
  ),
);
CardDescription.displayName = "CardDescription";

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />,
);
CardContent.displayName = "CardContent";

const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex items-center p-6 pt-0", className)} {...props} />
  ),
);
CardFooter.displayName = "CardFooter";

export { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle };
Source: common components and hook
tsx
import { Loader2 } from "lucide-react";

interface SpinnerProps {
  label?: string;
  /** Center in the whole viewport (used while the session is being restored). */
  fullPage?: boolean;
}

export function Spinner({ label = "Loading…", fullPage = false }: SpinnerProps) {
  const content = (
    <div role="status" className="flex items-center justify-center gap-2 text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
  return fullPage ? (
    <div className="flex min-h-screen items-center justify-center">{content}</div>
  ) : (
    <div className="py-10">{content}</div>
  );
}
tsx
import type { ReactNode } from "react";

interface PagePlaceholderProps {
  title: string;
  description: string;
  children?: ReactNode;
}

/** Temporary page body used until the real feature is built. */
export function PagePlaceholder({ title, description, children }: PagePlaceholderProps) {
  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
        {title}
      </h1>
      <p className="mt-1 text-muted-foreground">{description}</p>
      {children ? <div className="mt-6">{children}</div> : null}
    </section>
  );
}
ts
import { useEffect } from "react";

/** Sets `document.title`. Screen readers announce it on every navigation. */
export function useDocumentTitle(title?: string | null): void {
  useEffect(() => {
    document.title = title ? `${title} · EduConnect` : "EduConnect";
  }, [title]);
}
Source: layouts
tsx
import { Outlet } from "react-router-dom";

import { TopNav } from "@/components/layout/TopNav";

export function AppLayout() {
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
tsx
import { GraduationCap, Home, ListTodo, LogOut, Shield, User as UserIcon, type LucideIcon } from "lucide-react";
import { Link, NavLink } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/todo", label: "To-Do", icon: ListTodo },
  { to: "/classes", label: "Classes", icon: GraduationCap },
  { to: "/profile", label: "Profile", icon: UserIcon },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
  );

export function TopNav() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const items = user?.role === "admin" ? [...NAV_ITEMS, { to: "/admin", label: "Admin", icon: Shield }] : NAV_ITEMS;

  return (
    <header className="border-b bg-background">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2">
        <Link to="/" className="text-lg font-bold tracking-tight">
          EduConnect
        </Link>

        <nav aria-label="Main" className="order-last flex w-full gap-1 overflow-x-auto md:order-none md:w-auto">
          {items.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={linkClass}>
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          {user ? (
            <span className="hidden text-sm sm:inline">
              {user.full_name} <span className="text-muted-foreground">({user.role})</span>
            </span>
          ) : null}
          <Button variant="outline" size="sm" onClick={() => void logout()}>
            <LogOut aria-hidden="true" />
            Log out
          </Button>
        </div>
      </div>
    </header>
  );
}
tsx
import { ArrowLeft, BookOpenCheck, MessageSquare, Users, type LucideIcon } from "lucide-react";
import { Link, NavLink } from "react-router-dom";

import { cn } from "@/lib/utils";
import type { Classroom } from "@/types";

interface Item {
  suffix: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

const ITEMS: Item[] = [
  { suffix: "", label: "Stream", icon: MessageSquare, end: true },
  { suffix: "/classwork", label: "Classwork", icon: BookOpenCheck },
  { suffix: "/people", label: "People", icon: Users },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
  );

export function ClassroomSidebar({ classroom }: { classroom: Classroom }) {
  const base = `/classes/${classroom.id}`;
  return (
    <aside className="md:w-56 md:shrink-0">
      <Link
        to="/classes"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        All classes
      </Link>

      <h2 className="text-lg font-semibold leading-tight">{classroom.name}</h2>
      {classroom.section || classroom.subject ? (
        <p className="text-sm text-muted-foreground">
          {[classroom.section, classroom.subject].filter(Boolean).join(" · ")}
        </p>
      ) : null}
      {classroom.is_archived ? <p className="mt-1 text-sm font-medium text-destructive">Archived (read-only)</p> : null}

      <nav aria-label="Classroom" className="mt-3 flex gap-1 overflow-x-auto md:flex-col">
        {ITEMS.map(({ suffix, label, icon: Icon, end }) => (
          <NavLink key={label} to={`${base}${suffix}`} end={end} className={linkClass}>
            <Icon className="h-4 w-4" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      {classroom.my_role === "teacher" && classroom.join_code ? (
        <div className="mt-4 rounded-md border p-3 text-sm">
          <p className="text-muted-foreground">Join code</p>
          <code className="text-base font-semibold tracking-widest">{classroom.join_code}</code>
        </div>
      ) : null}
    </aside>
  );
}
tsx
import { Link, Outlet, useParams } from "react-router-dom";

import { getStatus } from "@/api/errors";
import { Spinner } from "@/components/common/Spinner";
import { ClassroomSidebar } from "@/components/layout/ClassroomSidebar";
import { useClassroom } from "@/features/classrooms/hooks";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

/** Sidebar layout for every /classes/:classroomId/* page. Loads the classroom once. */
export function ClassroomLayout() {
  const { classroomId = "" } = useParams();
  const { data: classroom, isPending, error } = useClassroom(classroomId);
  useDocumentTitle(classroom?.name);

  if (isPending) return <Spinner label="Loading class…" />;

  if (error || !classroom) {
    const missing = getStatus(error) === 404 || getStatus(error) === 422;
    return (
      <div role="alert" className="py-10 text-center">
        <h1 className="text-xl font-semibold">{missing ? "Class not found" : "Could not load this class"}</h1>
        <p className="mt-1 text-muted-foreground">
          {missing ? "It does not exist, or you are not a member." : "Please try again in a moment."}
        </p>
        <Link to="/classes" className="mt-4 inline-block text-primary underline-offset-4 hover:underline">
          Back to your classes
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 md:flex-row">
      <ClassroomSidebar classroom={classroom} />
      <div className="min-w-0 flex-1">
        <Outlet context={{ classroom }} />
      </div>
    </div>
  );
}
tsx
import type { ReactNode } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface AuthShellProps {
  title: string;
  description: string;
  children: ReactNode;
  footer?: ReactNode;
}

/** Centered card used by the login and register pages. */
export function AuthShell({ title, description, children, footer }: AuthShellProps) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <div className="w-full max-w-md">
        <p className="mb-4 text-center text-2xl font-bold tracking-tight">EduConnect</p>
        <Card>
          <CardHeader>
            <CardTitle>
              <h1>{title}</h1>
            </CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          <CardContent>{children}</CardContent>
        </Card>
        {footer ? <p className="mt-4 text-center text-sm text-muted-foreground">{footer}</p> : null}
      </div>
    </main>
  );
}
Source: classrooms feature
ts
import { api } from "@/api/client";
import type { Classroom } from "@/types";

export const classroomsApi = {
  list: (params?: { include_archived?: boolean }) =>
    api.get<Classroom[]>("/classrooms", { params }).then((r) => r.data),

  get: (id: string) => api.get<Classroom>(`/classrooms/${id}`).then((r) => r.data),
};
ts
import { useQuery } from "@tanstack/react-query";

import { classroomsApi } from "@/features/classrooms/api";

const root = ["classrooms"] as const;

export const classroomKeys = {
  all: root,
  list: () => [...root, "list"] as const,
  detail: (id: string) => [...root, "detail", id] as const,
};

export function useClassrooms() {
  return useQuery({ queryKey: classroomKeys.list(), queryFn: () => classroomsApi.list() });
}

export function useClassroom(id: string) {
  return useQuery({
    queryKey: classroomKeys.detail(id),
    queryFn: () => classroomsApi.get(id),
    enabled: Boolean(id),
  });
}
ts
import { useOutletContext } from "react-router-dom";

import type { Classroom } from "@/types";

/** The classroom loaded by `ClassroomLayout`, for its child pages. */
export function useClassroomContext(): { classroom: Classroom } {
  return useOutletContext<{ classroom: Classroom }>();
}
Source: pages
tsx
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/store/auth";

export function LoginPage() {
  useDocumentTitle("Sign in");
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      // GuestRoute redirects once the store has a user.
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Sign in"
      description="Use your EduConnect account."
      footer={
        <>
          No account?{" "}
          <Link to="/register" className="text-primary underline-offset-4 hover:underline">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate={false}>
        {error ? (
          <p role="alert" className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthShell>
  );
}
tsx
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { authApi } from "@/api/auth";
import { getErrorMessage } from "@/api/errors";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/store/auth";
import type { RegisterInput } from "@/types";

export function RegisterPage() {
  useDocumentTitle("Create account");
  const login = useAuthStore((s) => s.login);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<RegisterInput["role"]>("student");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    // Same rule as the backend: at least one letter and one digit.
    if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      setError("Password must contain at least one letter and one digit.");
      return;
    }

    setSubmitting(true);
    try {
      await authApi.register({ email: email.trim(), password, full_name: fullName.trim(), role });
      await login({ email: email.trim(), password }); // GuestRoute then redirects
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      description="Teachers create classes; students join them with a code."
      footer={
        <>
          Already registered?{" "}
          <Link to="/login" className="text-primary underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        {error ? (
          <p role="alert" className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <div className="space-y-2">
          <Label htmlFor="full_name">Full name</Label>
          <Input
            id="full_name"
            autoComplete="name"
            required
            maxLength={255}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={72}
            aria-describedby="password-hint"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p id="password-hint" className="text-xs text-muted-foreground">
            8-72 characters, with at least one letter and one digit.
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="role">I am a</Label>
          <select
            id="role"
            value={role}
            onChange={(e) => setRole(e.target.value as RegisterInput["role"])}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="student">Student</option>
            <option value="teacher">Teacher</option>
          </select>
        </div>
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Creating account…" : "Create account"}
        </Button>
      </form>
    </AuthShell>
  );
}
tsx
import { GraduationCap, ListTodo } from "lucide-react";
import { Link } from "react-router-dom";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/store/auth";

export function HomePage() {
  useDocumentTitle("Home");
  const user = useAuthStore((s) => s.user);

  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
        Welcome{user ? `, ${user.full_name}` : ""}
      </h1>
      <p className="mt-1 text-muted-foreground">Here is where your day starts.</p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Link to="/classes" className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Card className="h-full transition-colors hover:bg-accent/50">
            <CardHeader>
              <GraduationCap className="h-6 w-6 text-primary" aria-hidden="true" />
              <CardTitle className="text-lg">Your classes</CardTitle>
              <CardDescription>Open a class to see its stream, classwork and people.</CardDescription>
            </CardHeader>
          </Card>
        </Link>
        <Link to="/todo" className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Card className="h-full transition-colors hover:bg-accent/50">
            <CardHeader>
              <ListTodo className="h-6 w-6 text-primary" aria-hidden="true" />
              <CardTitle className="text-lg">To-Do</CardTitle>
              <CardDescription>Assignments and quizzes that are waiting for you.</CardDescription>
            </CardHeader>
          </Card>
        </Link>
      </div>
    </section>
  );
}
tsx
import { PagePlaceholder } from "@/components/common/PagePlaceholder";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function TodoPage() {
  useDocumentTitle("To-Do");
  return <PagePlaceholder title="To-Do" description="Your pending assignments and quizzes will appear here (GET /todo)." />;
}
tsx
import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { Spinner } from "@/components/common/Spinner";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useClassrooms } from "@/features/classrooms/hooks";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function ClassesPage() {
  useDocumentTitle("Classes");
  const { data, isPending, error } = useClassrooms();

  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
        Classes
      </h1>

      {isPending ? <Spinner label="Loading your classes…" /> : null}
      {error ? (
        <p role="alert" className="mt-4 text-destructive">
          {getErrorMessage(error)}
        </p>
      ) : null}

      {data && data.length === 0 ? (
        <p className="mt-4 text-muted-foreground">
          You are not in any class yet. Creating and joining classes comes in the next step.
        </p>
      ) : null}

      {data && data.length > 0 ? (
        <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((classroom) => (
            <li key={classroom.id}>
              <Link
                to={`/classes/${classroom.id}`}
                className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Card className="h-full transition-colors hover:bg-accent/50">
                  <CardHeader>
                    <CardTitle className="text-lg">{classroom.name}</CardTitle>
                    <CardDescription>
                      {[classroom.section, classroom.subject].filter(Boolean).join(" · ") || "No details"}
                    </CardDescription>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {classroom.my_role}
                      {classroom.is_archived ? " · archived" : ""}
                    </p>
                  </CardHeader>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/store/auth";

export function ProfilePage() {
  useDocumentTitle("Profile");
  const user = useAuthStore((s) => s.user);
  if (!user) return null; // ProtectedRoute guarantees a user

  const rows: [string, string][] = [
    ["Name", user.full_name],
    ["Email", user.email],
    ["Role", user.role],
    ["Member since", new Date(user.created_at).toLocaleDateString()],
  ];

  return (
    <section aria-labelledby="page-title" className="max-w-xl">
      <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
        Profile
      </h1>
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-lg">Your account</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-[8rem_1fr] gap-y-3 text-sm">
            {rows.map(([term, value]) => (
              <div key={term} className="contents">
                <dt className="text-muted-foreground">{term}</dt>
                <dd className="break-words font-medium">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-sm text-muted-foreground">Editing your profile (PATCH /users/me) comes in a later step.</p>
        </CardContent>
      </Card>
    </section>
  );
}
tsx
import { PagePlaceholder } from "@/components/common/PagePlaceholder";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

/** Only reachable for global admins (see RoleRoute in routes/index.tsx). */
export function AdminPage() {
  useDocumentTitle("Admin");
  return <PagePlaceholder title="Admin" description="Platform administration will live here." />;
}
tsx
import { Link } from "react-router-dom";

import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function ForbiddenPage() {
  useDocumentTitle("Access denied");
  return (
    <section role="alert" className="py-16 text-center">
      <h1 className="text-2xl font-semibold">403: Access denied</h1>
      <p className="mt-1 text-muted-foreground">Your account does not have permission to view this page.</p>
      <Link to="/" className="mt-4 inline-block text-primary underline-offset-4 hover:underline">
        Go home
      </Link>
    </section>
  );
}
tsx
import { Link } from "react-router-dom";

import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function NotFoundPage() {
  useDocumentTitle("Page not found");
  return (
    <section className="py-16 text-center">
      <h1 className="text-2xl font-semibold">404: Page not found</h1>
      <p className="mt-1 text-muted-foreground">That page does not exist.</p>
      <Link to="/" className="mt-4 inline-block text-primary underline-offset-4 hover:underline">
        Go home
      </Link>
    </section>
  );
}
tsx
import { PagePlaceholder } from "@/components/common/PagePlaceholder";
import { useClassroomContext } from "@/features/classrooms/context";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function StreamPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · Stream`);
  return (
    <PagePlaceholder
      title="Stream"
      description="Announcements and comments for this class will appear here (STEP 8 endpoints)."
    />
  );
}
tsx
import { PagePlaceholder } from "@/components/common/PagePlaceholder";
import { useClassroomContext } from "@/features/classrooms/context";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function ClassworkPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · Classwork`);
  return (
    <PagePlaceholder
      title="Classwork"
      description="Assignments, quizzes and materials for this class will appear here."
    />
  );
}
tsx
import { PagePlaceholder } from "@/components/common/PagePlaceholder";
import { useClassroomContext } from "@/features/classrooms/context";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function PeoplePage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · People`);
  return (
    <PagePlaceholder
      title="People"
      description="Teachers and students of this class will appear here (GET /classrooms/{id}/people)."
    />
  );
}

How to run and test
1. Install and start
bash
cd frontend
cp .env.example .env
npm install
npm run dev                  # http://localhost:5173
The backend must be running (docker compose up -d postgres redis, then uvicorn app.main:app --reload in backend/). Its default CORS_ORIGINS already allows http://localhost:5173.
bash
npm run build                # type-checks everything (tsc -b) and produces dist/
npm run preview              # serves the production build on :5173
Or with Docker: add the frontend service to docker-compose.yml, then run docker compose up --build frontend backend.
2. Manual test checklist
#	Do this	Expected
1	Open http://localhost:5173/classes while logged out	Redirected to /login
2	Register as a teacher	Auto-signed in, lands on Classes (the page you tried to open)
3	Look at the top nav	Home, To-Do, Classes, Profile; the active link is highlighted; your name and role are shown
4	Create a class via Swagger or curl (below), then reload /classes	A card appears; click it for the sidebar layout (Stream, Classwork, People, join code for teachers)
5	Open /classes/00000000-0000-0000-0000-000000000000	“Class not found”
6	Reload the page while signed in	Still signed in (session restored through /auth/me)
7	Press Tab on any page	The first focus stop is “Skip to main content”
8	Open /admin as a teacher	403: Access denied page
9	Promote yourself (below), reload, open /admin	Admin page appears, and an Admin link shows in the nav
10	Click Log out	Back at /login. In DevTools, localStorage["educonnect.auth.v1"] is gone
11	Open two tabs, log out in one	The other tab goes to /login within a moment
Create a class for step 4:
bash
BASE=http://localhost:8000/api/v1
T=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"YOUR_EMAIL","password":"YOUR_PASSWORD"}' | jq -r .access_token)
curl -s -X POST $BASE/classrooms -H 'Content-Type: application/json' -H "Authorization: Bearer $T" \
  -d '{"name":"Math 101","section":"A","subject":"Algebra"}' | jq .
Promote yourself for step 9:
bash
docker compose exec postgres psql -U educonnect -d educonnect -c \
  "update users set role='admin' where email='YOUR_EMAIL';"
3. Test the refresh-on-401 interceptor
1.In backend/.env set ACCESS_TOKEN_EXPIRE_MINUTES=1 and restart the API.
2.Sign in, open DevTools, and go to the Network tab.
3.Wait about 70 seconds, then click Classes.
4.You should see this sequence: 
oGET /classrooms → 401
oPOST /auth/refresh → 200
oGET /classrooms → 200
5.The page renders normally and the user never notices.
Then test the failure path. Run docker compose exec redis redis-cli FLUSHALL and delete the stored refresh token’s revocation entry if you like, or simply wait for the refresh token to expire. With a rejected refresh token, the next request clears the session and sends you to /login.
Parallel requests share one refresh. Open the page that fires several queries after the access token expired: you should see exactly one /auth/refresh call in the Network tab.
Troubleshooting
Problem	Fix
CORS error in the console	Add your frontend origin to CORS_ORIGINS in backend/.env and restart the API
Page is blank and the console says VITE_API_URL is undefined	You created .env after starting Vite. Restart npm run dev
Cannot find module '@/...'	The alias exists in three places: vite.config.ts, tsconfig.json and tsconfig.app.json. Check all three
Login works but you are bounced back to /login	/auth/me is failing. Check the Network tab, and check the backend is on localhost:8000
Logged out after every refresh in Docker	The VITE_API_URL in docker-compose.yml must point at the host-published port (localhost:8000), because the browser calls it
npx shadcn add ... rewrites Tailwind to v4	Use the Tailwind 3 compatible CLI: npx shadcn@2.3.0 add dialog
npm ci fails in the Dockerfile	Run npm install once locally to create package-lock.json and commit it
429 on login	The backend allows 10 logins per minute per IP. Wait a minute
tsc -b complains about unused variables	noUnusedLocals is on. Remove the unused import or variable
What is placeholder in this step
The Stream, Classwork, People, To-Do and Admin pages show placeholder text. The routes, layouts and guards around them are real.
The features/*/.gitkeep folders (assignments, quizzes, materials, announcements, todo, notifications, files) are empty on purpose. The notifications WebSocket client will use env.WS_URL and the first-message auth from STEP 11.
Creating and joining classes from the UI comes in the next frontend step.
Reply NEXT for STEP 14.
STEP 14 — Auth Pages + API Wiring (Frontend)
text
STEP 14: Auth UI + API layer.

- src/api/auth.ts (register, login, refresh, me)
- pages/Login.tsx, pages/Register.tsx (role picker: teacher/student)
- pages/Home.tsx (list classrooms as cards + "Join class" + "Create class" buttons)
- src/features/classrooms/api.ts + hooks with TanStack Query (useClassrooms, useCreateClassroom, useJoinClassroom).
- Handle token storage in memory + localStorage fallback; auto-refresh on 401.
```
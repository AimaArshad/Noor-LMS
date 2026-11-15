# Noor LMS — frontend

React 19 + TypeScript + Vite + Tailwind CSS v4. The API contract in `src/api/types.ts` is
generated from the live backend and is the source of truth for every request/response shape.

## Setup

The app reads its URLs from the environment only; there are no hard-coded fallbacks.

```bash
cd frontend
cp .env.example .env      # then edit if your backend is not on localhost:8000
npm install
npm run dev               # http://localhost:5173
```

`.env` (git-ignored):

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

A missing variable throws at startup with a message pointing back at `.env.example`, rather
than silently talking to the wrong server.

## Scripts

| Script              | What it does                                                   |
| ------------------- | -------------------------------------------------------------- |
| `npm run dev`       | Vite dev server with HMR on port 5173                          |
| `npm run build`     | `tsc -b` (no emit) followed by the production build to `dist/` |
| `npm run typecheck` | Types only                                                      |
| `npm run lint`      | oxlint                                                          |
| `npm run gen:api`   | Regenerate `src/api/types.ts` from `http://localhost:8000/api/v1/openapi.json` |

`npm run gen:api` needs the backend running. After regenerating, fix any compile errors it
causes in `src/types/index.ts` — that file is the only place that maps schema names to app
names.

## Layout

```
src/
├── api/           axios client (auth header + single-flight refresh-on-401), errors, generated types
├── components/    ui/ primitives, common/ shared widgets, layout/ app shell and nav
├── features/      one folder per domain (classrooms, assignments, quizzes, ...)
├── hooks/         shared hooks (document title, ...)
├── lib/           env, query client, class-name helper
├── pages/         route components
├── routes/        route table and guards (GuestRoute, ProtectedRoute, RoleRoute)
├── store/         zustand auth store (tokens mirrored to localStorage)
└── types/         app-level aliases over the generated schemas
```

## Docker

`docker compose up -d frontend` runs the `dev` target on port 5173 with the values from
`docker-compose.yml` (Vite inlines `VITE_*` at build time, so the `prod` target takes them as
build args).

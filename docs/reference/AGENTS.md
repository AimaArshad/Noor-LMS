# Project Rules for EduConnect

## Architecture
- Frontend: React + TypeScript + Vite + Tailwind CSS v4, located in `frontend/`.
- Backend: FastAPI in `backend/`, running at http://localhost:8000.
- NEVER edit anything inside `backend/`. It is read-only.

## Source of truth
- All API types are in `frontend/src/api/types.ts`, generated from the live backend's
  /openapi.json. If reference code disagrees with types.ts, **types.ts always wins**.

## Reference implementation
- `docs/reference/step13.md` … `step19.md` contain a reference frontend implementation.
- Treat it as a STARTING POINT, not gospel.
- Before applying any of it, verify every endpoint path, field name, and payload shape
  against `frontend/src/api/types.ts`. Report mismatches instead of guessing.

## Accessibility & Blind Mode (non-negotiable)
- Every feature must work for sighted students AND Blind Mode students.
- Every action must end in a spoken/announced result (aria-live regions).
- Use real semantic `<button>` and `<a>` elements — never clickable `<div>`s.
- Every voice command must have a keyboard equivalent.
- Contrast must follow `docs/ui-ux-design-brief.md`.

## Working style
- Plan first, then build. Make small changes.
- After each change, confirm `npm run dev` compiles with no errors.
- Commit after every completed step.
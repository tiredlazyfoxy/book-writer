# 002.frontend-scaffold — Frontend scaffold
<!-- roadmap:start -->
- **Stage:** 0.scaffold · **Track:** multi-step · **Size:** M
- **Depends on:** `001.backend-scaffold`

## Definition
Stand up the Vite multi-page frontend as a runnable, typechecking skeleton
with the three entries (User `/`, Admin `/admin`, Login `/login`), MobX +
Mantine wired, the `src/api/` layer (typed fetch, `ApiError` normalization,
the SSE reader pattern), and theming. `npm run dev` loads each entry;
`npm run build` (tsc + vite) is clean; end-to-end wiring is proven by calling
the backend health endpoint through `src/api/`.

## Scope
**In:** package.json + Vite MPA config (3 html entries); TS strict; Mantine
`theme.ts` + `global.css`; MobX baseline + the observer/state-class convention
bootstrapped on a trivial page; `src/api/` (client, `ApiError`, `sse.ts`);
`src/types/` seed; folder layout `src/{api,types,utils,components,user,admin,
login}`; Vite `/api` dev proxy → :8185.
**Out:** login form/auth (004), any real page or feature, routing beyond a
placeholder.

## Open questions for the planner
- Does the scaffold include a login-screen *shell* (no auth) or a bare placeholder?
- Where do dev vs prod nginx configs live?
<!-- roadmap:end -->

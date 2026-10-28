# APP-3 — Existing experiment workbench status

**Status:** RC5 Research Workbench implementation PASS for local Stub flows; real service and WARDEN execution remain NOT_RUN / BLOCKED.

> The RC3 notice described below is historical; the RC5 workbench and current UI behavior are recorded at the end of this file.

## Reuse and change

- Reused `ExperimentsPage`, shared `Card`/`Badge`, existing experiment DTOs, and the current experiment comparison flow.
- Added one gate notice. It reports the published Study metadata/run-level operations as `STATIC_ONLY`, live HTTP and research execution as `NOT_RUN`, and the upstream WARDEN Live Gate as `BLOCKED`.
- The gate explains that Study registration has no upstream idempotency contract, analysis arrays/source refs are not independently provenance-verified, and paired run routes are not bound to Study/Arm records.
- No synthetic Study rows, arm matrix, SRR/BER/U values, zero-filled metrics, effects, or causal claims are rendered.

## Validation and rollback

| Command | Result |
| --- | --- |
| `npm run test -- src/pages/__tests__/experiments-reports.test.tsx` | PASS; exit 0; 6 tests |
| `npm run typecheck` | PASS; exit 0 |
| `npm run lint` | PASS; exit 0 |
| `npm run test` | PASS; exit 0; 13 files, 69 tests |
| `npm run build` | PASS; exit 0; Vite reports a 630.47 kB minified JS chunk warning |
| `npm run e2e` | PASS; exit 0; 2 Playwright tests using deterministic App fixtures; not Live AgentGuard/WARDEN evidence |

Rollback is a revert of the historical capability notice.

## RC5 update — 2026-10-28

- Added `/research` to the existing React Router and navigation. Page title now comes from route `handle` metadata.
- The page reads the AgentGuard RC5 capability report, labels `LIVE`/`SYNTHETIC`/`UNAVAILABLE`, and renders upstream status, blockers, source version, and observed time. The project selector is part of the route state; study query keys include `project_id`.
- Added a preregistration form for RC5 required fields, track and JSON arm definitions. It performs registration only; no fake run or result is displayed. Ambiguous requests offer an explicit retry using the same payload and key.
- The Study table is populated from the App's project mapping, and detail, integrity and analyses are shown only for mapped IDs. Empty analyses remain empty. Execution and measured analysis write remain visibly blocked.
- Added React tests for synthetic capability state, project-bound submission, CSRF and idempotency headers, and honest empty/blocker states. Current complete frontend command results are recorded in APP-5.

# APP-3 — Existing experiment workbench status

**Status:** PASS for truthful static gate display; real Study/Arm display remains BLOCKED.

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

Rollback is a revert of the capability notice; no new route, data store, or navigation entry exists.

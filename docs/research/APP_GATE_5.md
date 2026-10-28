# APP-5 — RC5 integration and acceptance (2026-10-28)

**Current status:** RC5 static contract, project-scoped Study preregistration/read paths, and local automated checks are implemented. A read-only HTTP smoke through the local AgentGuard service and QWB BFF passed on 2026-10-29. Project-scoped Study writes were not attempted; the WARDEN Live Gate remains **BLOCKED**. This record supersedes the historical RC3 pin and results below.

## Fixed upstream sources

- Runtime/API implementation snapshot: AgentGuard `d85aa97e1566e2c50816f2ade3129235266ec704`, version `1.1.0rc5`.
- Current upstream branch head: `c67c7f1f186aeec6d95d6a6c1c0a48bb1a84ea38` (documentation-only commit after the implementation snapshot).
- OpenAPI source: `d85aa97e1566e2c50816f2ade3129235266ec704`; raw SHA-256 `605a9cd95f0edeedd4d7235fe46a4a6d8c99ffeb4aab00e2e7f51b2addc2a6b7`; canonical SHA-256 `b7722098b9adac87386a62325b19240e5c7024f704d7024a38ad3a2fb6ca8acd`; 87 paths and 99 operations.
- Upstream [AgentGuard CI run 40704083443](https://github.com/hauyer/AgentGuard/actions/runs/40704083443) passed on the current branch head across Python 3.11, 3.12, and 3.13.
- Local runtime checkout `../AgentGuard` is clean at `c67c7f1f186aeec6d95d6a6c1c0a48bb1a84ea38`; it is one documentation-only commit after implementation pin `d85aa97e1566e2c50816f2ade3129235266ec704`.
- RC4 implementation baseline: `9d1c1dc9331f4ce168aab29b860c94b9d65a8321`; its OpenAPI snapshot is preserved separately. RC4→RC5 has no path or operation additions/removals. The four Study operations have contract changes and seven schemas changed; all 33 previously supported operation objects remain structurally identical after JSON parsing.
- App supports the existing 33 operations plus six RC5 operations: capability report, Study list/register/detail/integrity/analysis-list. The global upstream Study list is never exposed as a project list; local ownership mappings gate every Study read.

## RC5 implementation and limits

- Added a durable project-to-Study registration record with hashed idempotency key, request fingerprint/body, upstream response, source metadata, and ambiguity state. Registration requires an Idempotency-Key and analyst CSRF; writes are not automatically retried. An uncertain POST can be explicitly retried with the same key and exact request, relying on the RC5 idempotency contract.
- Added project-scoped capability, registration, list, detail, integrity, and analysis-list BFF endpoints. Cross-project and unlinked upstream Study IDs remain invisible. No analysis-write, run, artifact-content, or WARDEN execution endpoint is exposed.
- Added the Research Workbench with an immutable pre-submit JSON summary and explicit confirmation, project-local Study list/details, source labels, and WARDEN/analysis blockers. The form captures the RC5 primary/secondary outcomes, analysis/multiplicity methods, alpha, paired/family counts, matching variables, seed, inclusion/exclusion rules, stopping/missing-data/deviation rules, protocol/code revisions, track, and arm definitions/parameter hashes. Edits invalidate the preview and rotate the idempotency key. No synthetic Study or research metric is invented.
- The guide’s RC4 pin is stale. RC5 still has 87 paths and 99 operations; four Study operations and seven schemas changed. `track` and `arms` already existed in RC4. RC5 adds registration metadata and idempotency for Study and analysis POSTs. `measured` analysis is still rejected until WARDEN artifact content is verified.

## Local live connection (2026-10-29)

- Started the local AgentGuard checkout on `127.0.0.1:8000`, bound to loopback, using a new temporary data directory and reporting its actual build commit `c67c7f1f186aeec6d95d6a6c1c0a48bb1a84ea38`. API/operator/approval tokens and `AGENTGUARD_WARDEN_URL` were explicitly empty; no user `.env` or AgentGuard repository files were changed.
- Direct HTTP checks passed for `/health`, `/v1/system/health`, `/v1/system/identity`, `/v1/system/readiness`, `/v1/system/capabilities`, `/v1/research/capabilities`, and `/openapi.json`. The service reports `1.1.0rc5`, `backend_mode=synthetic`, and `WARDEN_URL_NOT_CONFIGURED`.
- The runtime OpenAPI response has 87 paths / 99 operations. Its raw response SHA-256 is `3d70ee39de6f8d6329d6d3d20335d0a47fde32d0c9185f5b5c2345cfe783c1a9`; after parsing, it exactly equals the pinned snapshot, and the canonical SHA-256 matches `b7722098b9adac87386a62325b19240e5c7024f704d7024a38ad3a2fb6ca8acd`. The live contract checker passed and verified all 39 App-pinned operations. The response identity reports the actual local build commit; the API itself does not expose that commit in OpenAPI.
- Started the QWB BFF on `127.0.0.1:8001` with the local AgentGuard base URL and development auth disabled, then the Vite UI on `127.0.0.1:5173` proxied to that BFF. `/api/health` and `/api/research/capabilities` returned HTTP 200 through BFF; the same capability response also returned HTTP 200 through Vite proxy.
- The BFF has no `DATABASE_URL` in this local run, so audit events are memory-buffered and project-scoped Study registration/lookup was not exercised against the live service. No Study was created. The live report contains 11 capabilities with `backend_status=not_configured`; WARDEN-backed execution and measured analysis remain **BLOCKED**.
- AgentGuard readiness currently formats a monotonic timer as a UTC wall-clock timestamp, so its `generated_at`/`last_checked_at` values appear in 1970. The readiness statuses are readable, but those timestamps are not valid observation times. This defect is in the AgentGuard checkout and was not changed here.

## Verification results

| Check | Result |
| --- | --- |
| `python scripts/check_agentguard_contract.py --offline-only` | PASS; pinned RC5 raw/canonical hashes, version, 87 paths, operation diff, 33 legacy operations, and RC5 request shapes verified |
| Targeted backend contract/migration/research/client tests | PASS; initial combined run 48 passed; after the idempotency-race/audit changes, research/client run 34 passed |
| Full backend `py -3.12 -m pytest -o addopts='' -q` | PASS; exit 0; 286 passed, 1 skipped (287 collected; 973.22 seconds). The skipped case is the PostgreSQL concurrency test because `QWB_TEST_POSTGRES_URL` is not configured. This final run includes the idempotency-race and audit fixes. |
| `py -3.12 -m ruff check .` | PASS |
| `py -3.12 ..\scripts\verify_migrations.py` | PASS; empty SQLite database upgraded to head, downgraded to base, upgraded again; `project_study_submissions` and required lock tables verified |
| `py -3.12 -m pytest -q tests/test_postgres_loop_concurrency.py` | SKIP; no `QWB_TEST_POSTGRES_URL` is configured |
| `npm ci` | PASS; 381 packages installed; npm reported the existing blocked `esbuild` install-script approval warning |
| `npm run typecheck` / `npm run lint` | PASS |
| `npm run test` | PASS; 14 files, 71 tests |
| `npm run build` | PASS; Vite warns that the 653.93 kB minified JavaScript chunk exceeds 500 kB |
| `npm run e2e` | PASS on the final isolated run; 2 Playwright tests using local deterministic fixtures. Covers Study pre-registration preview/confirmation and project binding, plus both the system overview and Research Workbench at 1440×900, 1366×768, 1024×768, and 390×844 with no page-wide horizontal overflow. An initial parallel attempt failed under concurrent checks; a later RC5 E2E run exposed that the Research page requested 500 projects while the BFF maximum is 200. The request limit and test navigation/locator steps were corrected, then the isolated suite passed. |
| Docker Compose production config | PASS with temporary placeholder values for required deployment secrets; repository `.env` was not read |
| Docker image build | NOT_RUN; Docker Desktop Linux engine pipe is unavailable |
| `git diff --check` | PASS |
| Local AgentGuard HTTP smoke / service identity / readiness | PASS; local RC5 endpoints, actual build identity, 87/99 OpenAPI, canonical snapshot equality, and 39 App-pinned operations verified. BFF and Vite-proxied capability reads also returned HTTP 200. No write request was sent. |
| Project-scoped Study POST/lookup against local AgentGuard | NOT_RUN; the BFF has no `DATABASE_URL`, so no durable project/ownership mapping was available |
| External or credentialed AgentGuard deployment smoke | NOT_RUN; only the loopback local service was configured |
| WARDEN runtime / measured research validation | **BLOCKED** upstream; Stub and offline checks do not represent live execution |
| QWB-App GitHub Actions CI | NOT_RUN; this work remains local and has not been pushed |

## UI screenshots

Playwright generated system overview screenshots in `frontend/test-results/smoke-console-boots-and-shows-system-status-chromium/` and Research Workbench screenshots in `frontend/test-results/investigation-workflow-log-8424c-ation-exports-and-isolation-chromium/`, each at `1440x900`, `1366x768`, `1024x768`, and `390x844`. The mobile navigation drawer is also captured. Desktop and mobile views of both pages were visually inspected; E2E checks found no page-wide horizontal overflow.

## Historical acceptance record

The sections below document earlier RC3/RC2 acceptance and remain for audit history; their old pins, counts, and statuses do not describe the current RC5 worktree.

# APP-5 — Tests and delivery (historical RC3 record)

**Status:** Local implementation and verification complete; live integration remains blocked.

## Fixed pin and safety boundary

- AgentGuard runtime/API source: `9a8ee1f5e78a0b254c17ea66ac5b140aa7e1e89a`, `1.1.0rc3`.
- Raw OpenAPI SHA-256: `fadab4d701d23fabda785413cf0c4536fcffec521ea09cbe6ad73a417c15de1e`.
- Canonical OpenAPI SHA-256: `52ad0d5dc175e58759196588d1c4ab5b45e82751f882c82ed8540cb963d942f6`.
- Upstream CI run `40336215846`: success. App baseline CI run `40336150184`: success on the unmodified starting commit.
- Live OpenAPI/identity/readiness and HTTP smoke: **NOT_RUN**. WARDEN Live Gate: **BLOCKED**. True paired execution/model validation: **NOT_RUN**.

## Commands and results

| Command | Result |
| --- | --- |
| `python scripts/check_agentguard_contract.py --offline-only` | PASS; exit 0; RC3 raw/canonical hash, version, 86 paths, 98 operations, candidate operations, and all supported request shapes |
| `python -m pytest tests/test_contract_snapshot.py -q` | PASS; exit 0; 9 tests |
| `python -m pytest -q` (backend) | PASS; exit 0; 281 passed, 1 skipped (282 collected) |
| `ruff check .` (backend) | PASS; exit 0; All checks passed |
| `python ../scripts/verify_migrations.py` (backend) | PASS; exit 0; SQLite upgrade/current/downgrade/re-upgrade; required tables and active Loop unique lock present |
| `python -m pytest tests/test_postgres_loop_concurrency.py -q` | SKIP; exit 0; 1 test skipped because `QWB_TEST_POSTGRES_URL` is not configured |
| `npm ci` | PASS; exit 0; 381 packages installed; npm reports the existing esbuild install-script approval warning |
| `npm run typecheck` | PASS; exit 0 |
| `npm run lint` | PASS; exit 0 |
| `npm run test` | PASS; exit 0; 13 files, 69 tests |
| `npm run build` | PASS; exit 0; minified JS chunk is 630.47 kB and triggers Vite's >500 kB warning |
| `npm run e2e` | PASS; exit 0; 2 Playwright tests with deterministic local fixtures |
| `docker compose config --quiet` | PASS; exit 0 |
| `docker compose build` | FAIL to start; exit 1 because the local Docker Desktop Linux engine pipe is unavailable (`dockerDesktopLinuxEngine`). This is an environment limitation; image build was not completed. |
| `python scripts/live_agentguard_check.py --help` | PASS; exit 0; script usage verified |
| Live AgentGuard HTTP smoke | **NOT_RUN**; base URL and API/operator credentials are absent |
| `git diff --check` | PASS; exit 0; Git emitted only its normal `core.autocrlf` LF→CRLF working-copy notices for text files |

No current-commit App GitHub Actions run was triggered because changes remain local and this task does not push. Baseline App CI run `40336150184` passed; upstream AgentGuard CI run `40336215846` passed for the pinned source commit.

## Delivery boundary

Changes are confined to the App checkout. No upstream repository is modified, and no push, merge, or deployment is performed.

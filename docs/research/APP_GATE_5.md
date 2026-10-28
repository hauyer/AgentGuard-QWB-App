# APP-5 — Tests and delivery

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

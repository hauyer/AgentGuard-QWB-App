# APP-1 — Upstream publish and static pin

**Status:** PASS for static compatibility; live release gate remains closed.
**Runtime/API source pin:** AgentGuard `9a8ee1f5e78a0b254c17ea66ac5b140aa7e1e89a`, `1.1.0rc3`.
**Latest upstream branch documentation head checked:** `a5d5603cc653e17025038f3eb0606bc28d8bbd70` (documentation-only acceptance follow-up).
**API source remains separate in the version contract**, even though runtime and OpenAPI currently point to the same code commit.

## Evidence

- Exact runtime/API source commit `9a8ee1f…` passed [AgentGuard CI run 40336215846](https://github.com/hauyer/AgentGuard/actions/runs/40336215846), Python 3.11/3.12/3.13.
- The RC2→RC3 runtime commit changes the WARDEN adapter's request/response validation, paired-execution gates, evidence provenance, and readiness diagnostics. The follow-up branch head `a5d5603…` is one docs-only commit later; pinning the code commit with its own passing CI avoids implying the documentation commit is a separate runtime release.
- RC2→RC3 parsed JSON comparison: only `info.version` changed; both snapshots contain 86 paths and 98 operations. No operation or schema was added or removed in this version bump.
- All 33 App-supported operations retain their request, response, security, pagination, and idempotency contracts.
- RC3 raw snapshot size: 237,425 bytes; raw SHA-256: `fadab4d701d23fabda785413cf0c4536fcffec521ea09cbe6ad73a417c15de1e`.
- Canonical SHA-256: `52ad0d5dc175e58759196588d1c4ab5b45e82751f882c82ed8540cb963d942f6`; algorithm matches AgentGuard identity (sorted keys, compact separators, unescaped Unicode, UTF-8).
- The RC1 and RC2 snapshots remain checked in. RC2 is the direct rollback pin.
- RC2 already publishes Study registration/list/detail/integrity/analysis routes and run-scoped paired/intervention routes. They are static candidates only: no live service evidence, no Study project ownership mapping, no upstream Study POST idempotency, and no verified real paired executor. Study analysis accepts caller-supplied values whose refs/hashes do not prove provenance.

## Not run / blocked

- `/openapi.json`, `/v1/system/identity`, `/v1/system/readiness`, and HTTP smoke against a deployed target: **NOT_RUN**.
- True WARDEN execution, Probe/model validation, paired intervention, and causal validation: **NOT_RUN**; upstream WARDEN Live Gate: **BLOCKED**.
- Static route publication does not mark any Study operation `LIVE_VERIFIED`.

## Commands and results

| Command | Result |
| --- | --- |
| `python scripts/check_agentguard_contract.py --offline-only` | PASS; exit 0; RC3 raw/canonical hashes, 86 paths, 33 supported operations and strict RC2→RC3 diff |
| `python -m pytest tests/test_contract_snapshot.py -q` | PASS; exit 0; 9 passed after RC3 tests were added |

## Rollback

Restore the RC2 runtime/source pin `63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc` and select `integration-data/agentguard-openapi-63fe1b5.json`. Keep the RC3 snapshot and diff report for audit.

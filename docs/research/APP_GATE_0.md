# APP-0 — Baseline, permissions, and pin

> Historical baseline findings below are retained. RC5 pin and implementation supersede the earlier no-Study-mapping statement; see the RC5 update at the end.

**Status:** PASS for repository baseline and contract inventory.
**Audit start:** `74627b234a86ef13615e90346e0c8f3a3c86fc7e` on `feature/b25-b33-real-integration`.

## Reuse and baseline

- The worktree was clean before this gate's new audit file was created; no pre-existing user edits were overwritten.
- Existing app CI for the baseline commit passed: [run 40336150184](https://github.com/hauyer/AgentGuard-QWB-App/actions/runs/40336150184).
- RC2 pinned runtime/source was `63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc`, `1.1.0rc2`, 86 paths; the App supports 33 operations.
- Existing project ownership and RBAC are enforced through `resource_access`, `project_service`, role/CSRF dependencies, and App audit events. The App currently has no Study-to-project table or mapping.
- Reuse choices and UI/API call sites are recorded in [`UI_REUSE_AUDIT.md`](UI_REUSE_AUDIT.md).

## Commands and results

| Command | Result |
| --- | --- |
| `git status --porcelain=v1` before audit | PASS; exit 0; empty |
| `git branch -avv` | PASS; exit 0; current branch and remote both at `74627b2` |
| `git rev-parse HEAD` | PASS; exit 0; `74627b234a86ef13615e90346e0c8f3a3c86fc7e` |
| `git log --oneline --decorate -30` | PASS; exit 0; history inspected |
| `python scripts/check_agentguard_contract.py --offline-only` on RC2 baseline | PASS; exit 0; 86 paths, 33 supported operations, request shapes |

## Three separate states

- **Static API compatibility:** verified from checked-in RC2/RC3 source snapshots.
- **Live HTTP availability:** `NOT_RUN`; no service URL/credentials are configured.
- **Model/Study execution readiness:** WARDEN Live Gate is `BLOCKED`; actual WARDEN, Probe, model, and paired execution remain `NOT_RUN`.

## Rollback

Use the retained RC2 snapshot and metadata in `integration-data/agentguard-openapi-63fe1b5.json`. No database or runtime data was changed by APP-0.

## RC5 update — 2026-10-28

The App now pins AgentGuard runtime/API source `d85aa97e1566e2c50816f2ade3129235266ec704` (`1.1.0rc5`) and records the documentation-only latest branch head separately. It retains exact RC4 and RC5 snapshots and tests the four-operation/seven-schema diff plus all prior 33 operations. Migration 0009 adds durable project Study links and submission intents. Static compatibility is checked; live HTTP smoke remains **NOT_RUN**, and WARDEN execution remains **BLOCKED**.

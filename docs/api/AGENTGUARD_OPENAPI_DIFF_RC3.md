# AgentGuard OpenAPI comparison: 1.1.0rc2 to 1.1.0rc3

**Verified:** 2026-10-28
**Method:** static comparison of the CI-passed AgentGuard source commit and checked-in OpenAPI snapshots. No live AgentGuard service was available.

## Fixed sources

| Item | RC2 baseline | RC3 candidate |
| --- | --- | --- |
| Runtime commit | `63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc` | `9a8ee1f5e78a0b254c17ea66ac5b140aa7e1e89a` |
| OpenAPI source commit | `63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc` | `9a8ee1f5e78a0b254c17ea66ac5b140aa7e1e89a` |
| API version | `1.1.0rc2` | `1.1.0rc3` |
| OpenAPI paths / operations | 86 / 98 | 86 / 98 |
| Raw snapshot SHA-256 | `2ce83660a67111a346a2de9772fcaec1938a4a5de713439de34a83e372b9a5e5` | `fadab4d701d23fabda785413cf0c4536fcffec521ea09cbe6ad73a417c15de1e` |
| Canonical JSON SHA-256 | `d0a04af3d87c9dca3b30aa7feed89f84447103ed9e8c32c063257c8214a25834` | `52ad0d5dc175e58759196588d1c4ab5b45e82751f882c82ed8540cb963d942f6` |

Canonical JSON uses the AgentGuard identity algorithm: sort object keys, compact separators, leave Unicode unescaped, encode as UTF-8, then hash with SHA-256. Raw hashing is over the original UTF-8/LF snapshot bytes. Both snapshots remain checked in.

The historical RC1/RC2 report used a different App serializer for its canonical digest (default JSON separators and ASCII escaping). The prior values `e2d6d9…` and `430a8115…` describe that older method; with the current AgentGuard identity algorithm the same unchanged snapshots produce `cf6967dc…` and `d0a04af3…`, respectively. Raw hashes remain unchanged; the version contract retains both pins and now records the canonicalization method explicitly.

The exact RC3 runtime/API source commit passed [AgentGuard CI run 40336215846](https://github.com/hauyer/AgentGuard/actions/runs/40336215846) for Python 3.11, 3.12, and 3.13. This confirms the source commit's CI result, not a running deployment, WARDEN execution, or model research run.

The runtime code diff from RC2 hardens WARDEN request/response validation, paired-executor gates, evidence provenance and readiness diagnostics. The current upstream branch head is a later documentation-only acceptance commit; the App pins the exact CI-tested runtime/API commit rather than a docs-only head.

## Contract diff

The parsed JSON objects differ only at `info.version`, from `1.1.0rc2` to `1.1.0rc3`. Both contain 86 paths and 98 operations. There are no added or removed operations or schemas. The App checker now compares the complete parsed document after excluding only that version field, in addition to checking the 33 App-supported operations' request/response/security contract and the raw/canonical hashes.

The RC3 implementation commit changes WARDEN integration/evidence and paired-experiment contracts and exports new JSON Schemas. These REST paths already existed in RC2 and are unchanged in RC3: `POST/GET /v1/studies`, Study detail/integrity/analysis routes, run-scoped `GET/POST /v1/runs/{run_id}/experiments/paired`, and `POST /v1/runs/{run_id}/interventions`. They remain outside the App-supported 33-operation contract.

The Study preregistration schema records protocol/outcome planning but has no track/Arm matrix or project ownership. Its POST operation has no upstream idempotency header. The analysis operation computes statistics over caller-supplied outcome arrays; source artifact references and hashes are not independent proof of provenance. The paired operation is tied to an existing run/design/action. AgentGuard's production API returns `PAIRED_REPLAY_UNAVAILABLE` for a real backend without a validated paired executor, and its API factory rejects direct paired-executor injection. The upstream WARDEN Live Gate remains `BLOCKED`. Existing `GET /v1/research/strategy-evaluations` is a separate persisted-evaluation resource.

## App integration decision

- Pin runtime commit and API-source commit separately to `9a8ee1f5e78a0b254c17ea66ac5b140aa7e1e89a`; both currently identify the RC3 source release.
- Keep verification `static_source_only`, live OpenAPI/identity/readiness `NOT_RUN`, and published Study registry routes `STATIC_ONLY` until live behavior and project ownership are verified.
- Keep four-layer remote execution `BLOCKED`; upstream WARDEN Live Gate remains `BLOCKED`, while true execution and model/Probe validation are `NOT_RUN`.
- Do not add BFF Study routes, remote write controls, study lifecycle storage, fake arms, or results. Existing strategy evaluations, project authorization, evidence, and reports retain their separate contracts.
- Preserve the RC2 snapshot as the rollback point and the older RC1 snapshot/diff as history.

## Validation boundary

- **PASS — static source comparison:** exact RC2→RC3 JSON delta is only `info.version`; path and operation counts match; hashes match the source file.
- **PASS — App contract compatibility:** all 33 App-supported operations retain their request, response, security, and pagination definitions.
- **NOT_RUN — live OpenAPI, identity, readiness, and HTTP smoke:** no target service/credentials were configured.
- **BLOCKED — WARDEN Live Gate:** no real WARDEN, Probe, paired intervention, causal validation, or model execution evidence exists.

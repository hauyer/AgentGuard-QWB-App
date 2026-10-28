# AgentGuard OpenAPI comparison: 1.1.0rc4 to 1.1.0rc5

**Current AgentGuard runtime/API source:** `d85aa97e1566e2c50816f2ade3129235266ec704` (`1.1.0rc5`).
**Latest checked branch head:** `c67c7f1f186aeec6d95d6a6c1c0a48bb1a84ea38`, one documentation-only commit after the API source.
**Upstream CI:** [AgentGuard CI run 40704083443](https://github.com/hauyer/AgentGuard/actions/runs/40704083443), success on Python 3.11, 3.12 and 3.13.
**Live HTTP smoke:** `NOT_RUN`. **WARDEN Live Gate:** `BLOCKED`.

## Frozen files and counts

| Item | RC4 baseline | RC5 source |
| --- | --- | --- |
| Snapshot file | `integration-data/agentguard-openapi-9d1c1dc.json` | `integration-data/agentguard-openapi-d85aa97.json` |
| Source commit | `9d1c1dc9331f4ce168aab29b860c94b9d65a8321` | `d85aa97e1566e2c50816f2ade3129235266ec704` |
| Version | `1.1.0rc4` | `1.1.0rc5` |
| Paths / operations | 87 / 99 | 87 / 99 |
| Raw file SHA-256 | `f2b802fd7928bf2701bfbc65e4cf655c8f801a465fe6dd853f938e9d8f75b978` | `605a9cd95f0edeedd4d7235fe46a4a6d8c99ffeb4aab00e2e7f51b2addc2a6b7` |
| Canonical JSON SHA-256 | `09b21ab3cd1e95dd3073142e4274b387ffb43689437be3fa60ad0939403f7894` | `b7722098b9adac87386a62325b19240e5c7024f704d7024a38ad3a2fb6ca8acd` |

The RC5 snapshot was fetched from the upstream code commit and retained byte-for-byte. The branch-head commit `c67c7f1` changes documentation only; it is the CI-verified current branch head, while `d85aa97` remains the exact runtime and API snapshot source. The two commits are recorded separately in [`contracts/agentguard-version.json`](../../contracts/agentguard-version.json).

## Exact API delta

No paths or operations were added or removed. Four operation objects changed:

| Operation | RC5 change |
| --- | --- |
| `GET /v1/studies` | Adds `offset`, `track`, `sort_by` (`registered_at` or `title`) and `sort_order` (`asc` or `desc`). |
| `GET /v1/studies/{study_id}/analyses` | Adds `limit`, `offset`, `evidence_mode` (`synthetic`, `script_replay`, `observed`, `measured`) and `sort_order`. |
| `POST /v1/studies` | Adds optional `Idempotency-Key`, 1–128 characters matching `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`. RC5 also documents conflict/error responses with typed details and persistent registry failure cases. |
| `POST /v1/studies/{study_id}/analyses` | Adds the same optional `Idempotency-Key` contract and declares that measured outcomes remain rejected until WARDEN artifacts are verified. |

Seven existing schemas changed: `RegisteredStudy`, `ResearchCapabilityItem`, `StudyAnalysisReport`, `StudyAnalysisRequest`, `StudyArmAnalysisInput`, `StudyRegistrationRequest`, and `WardenAuditRequest`. RC5 adds Study/runtime provenance fields including `dataset_version`, WARDEN contract/runtime/mode identifiers, capture targets, approval requirements, and supersession metadata; capability references now include source API version and evidence/operation/contract references; analysis reports make planned pair and family counts required and add source-validation state. Required preregistration fields remain unchanged. Track and arms were already present in the preceding snapshot and are not attributed to this RC5 delta.

The App checker compares the complete changed-operation and changed-schema lists against the retained RC4 snapshot. All previous 33 App-supported operations remain byte-for-JSON-object identical. The App contract now contains 39 supported upstream operations: the existing 33, the RC5 research capability report, and the five project-scoped Study registry operations used by the BFF.

## App integration and safety boundary

- The BFF exposes `GET /api/research/capabilities` and project-scoped Study list, preregistration, detail, integrity and analysis-list routes. Every project route checks membership before looking up a Study.
- The BFF persists a project mapping and the normalized request intent before upstream registration. It hashes caller idempotency keys at rest and derives a stable RC5 upstream key. POST requests are never retried by the HTTP client. An explicit same-body, same-key request can safely recover `SUBMISSION_AMBIGUOUS` or a persisted in-flight intent under RC5 semantics.
- The project list is built only from App-owned mappings and is labeled `RECORDED`; it never returns the upstream global Study index. Detail, integrity and analysis-list calls are made only after a local mapping check.
- Analysis writes are not exposed. The upstream route accepts caller-supplied values and artifact references are not independent proof of source content. RC5 measured mode remains blocked until real WARDEN artifact contents are verified.
- Study registration records protocol intent; it does not start a run. Run-scoped interventions, Probe/SAE workflows and true four-layer execution remain blocked. The App does not produce sample counts, effects, causal conclusions or synthetic Study rows.

## Verification

The offline contract checker verifies both snapshots' raw and canonical hashes, the 87-path/99-operation inventory, the exact four-operation/seven-schema diff, all legacy operation objects, RC5 pagination and idempotency headers, and the measured-analysis gate. Tests and current command results are recorded in [`APP_GATE_5.md`](../research/APP_GATE_5.md).

Static contract checks and deterministic Stub tests do not establish a deployed AgentGuard service, operator credential validity, real identity/readiness, artifact provenance, or WARDEN execution. Those remain `NOT_RUN` or `BLOCKED` as stated above.

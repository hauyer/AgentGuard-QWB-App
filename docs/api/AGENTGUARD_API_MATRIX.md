# AgentGuard API Matrix

**Pinned runtime:** `d85aa97e1566e2c50816f2ade3129235266ec704` (`1.1.0rc5`)
**OpenAPI source:** `d85aa97e1566e2c50816f2ade3129235266ec704`; `87` paths and `99` operations. Latest branch head `c67c7f1f186aeec6d95d6a6c1c0a48bb1a84ea38` is a documentation-only commit after this code snapshot.
**Verification:** RC4→RC5 static source comparison and deterministic App tests; live HTTP smoke, identity, and readiness are **NOT_RUN**. See [RC5 OpenAPI diff](AGENTGUARD_OPENAPI_DIFF_RC5.md), [RC3](AGENTGUARD_OPENAPI_DIFF_RC3.md), [RC2](AGENTGUARD_OPENAPI_DIFF_RC2.md), and the machine-readable [version contract](../../contracts/agentguard-version.json).

## App-supported endpoints

The listed operations are the App's current supported contract. A contract match does not imply that a real WARDEN or model runtime is available.

| AgentGuard route | Method | App contract status |
| --- | --- | --- |
| `/v1/system/health` | `GET` | Contracted in BFF |
| `/v1/system/readiness` | `GET` | Contracted in BFF |
| `/v1/system/capabilities` | `GET` | Contracted in BFF |
| `/v1/kernel/status` | `GET` | Contracted in BFF |
| `/v1/investigations/options` | `GET` | Contracted in BFF |
| `/v1/scenarios` | `GET` | Contracted in BFF |
| `/v1/investigations` | `POST` | Contracted in BFF |
| `/v1/investigations` | `GET` | Contracted in BFF |
| `/v1/investigations/{request_id}` | `GET` | Contracted in BFF |
| `/v1/investigations/{request_id}/timeline` | `GET` | Contracted in BFF |
| `/v1/investigations/{request_id}/interaction-graph` | `GET` | Contracted in BFF |
| `/v1/runs/{run_id}/findings` | `GET` | Contracted in BFF |
| `/v1/runs/{run_id}/hypotheses` | `GET` | Contracted in BFF |
| `/v1/runs/{run_id}/investigation` | `GET` | Contracted in BFF |
| `/v1/evidence/investigations/{request_id}` | `GET` | Contracted in BFF |
| `/v1/defense-policies/{request_id}` | `GET` | Contracted in BFF |
| `/v1/defense-policies/{request_id}/preview` | `POST` | Contracted in BFF |
| `/v1/reports` | `GET` | Contracted in BFF |
| `/v1/reports/{run_id}` | `GET` | Contracted in BFF |
| `/v1/experiences` | `GET` | Contracted in BFF |
| `/v1/experiments` | `GET` | Contracted in BFF |
| `/v1/experiments/{experiment_id}` | `GET` | Contracted in BFF |
| `/v1/experiments/compare` | `POST` | Contracted in BFF |
| `/v1/investigation-loops` | `POST` | Contracted in BFF |
| `/v1/investigation-loops` | `GET` | Contracted in BFF |
| `/v1/investigation-loops/{loop_id}` | `GET` | Contracted in BFF |
| `/v1/investigation-loops/{loop_id}/decisions` | `GET` | Contracted in BFF |
| `/v1/investigation-loops/{loop_id}/evidence-changes` | `GET` | Contracted in BFF |
| `/v1/investigation-loops/{loop_id}/budget` | `GET` | Contracted in BFF |
| `/v1/research/strategy-evaluations` | `GET` | Contracted in BFF |
| `/v1/research/strategy-evaluations/{evaluation_id}` | `GET` | Contracted in BFF |
| `/v1/investigations/{request_id}/risk-analysis` | `GET` | Contracted in BFF |
| `/v1/system/audit-events` | `GET` | Contracted in BFF |
| `/v1/research/capabilities` | `GET` | Contracted; BFF returns upstream capability status and source mode |
| `/v1/studies` | `GET` | Contracted; BFF presents only local project mappings |
| `/v1/studies` | `POST` | Contracted; BFF persists project intent and requires idempotency |
| `/v1/studies/{study_id}` | `GET` | Contracted; BFF checks local project mapping first |
| `/v1/studies/{study_id}/integrity` | `GET` | Contracted; BFF checks local project mapping first |
| `/v1/studies/{study_id}/analyses` | `GET` | Contracted; BFF checks local project mapping first |

## Unexposed or blocked capabilities

- New in rc2 and not integrated: `GET /v1/system/identity`, `POST /v1/investigation-loops/{loop_id}/reconcile`. Both remain candidate operations until live behavior is verified.
- `POST /v1/studies/{study_id}/analyses` is not exposed by the App. It accepts caller-supplied outcomes; source refs and hashes do not independently verify provenance. RC5 rejects `measured` results until WARDEN artifact contents are verified.
- The Study registry is exposed through project-scoped BFF routes backed by a local mapping and durable submission intent. RC5's optional upstream `Idempotency-Key` is used with an App-required key. Live service behavior remains **NOT_RUN**.
- Run-scoped paired/intervention routes are **BLOCKED** for real study execution. They require an existing run/design/action and do not map to Study/Arm records; the production AgentGuard API refuses a real paired run without a validated executor. WARDEN Live Gate remains **BLOCKED**.
- RC5 publishes protocol provenance and capture metadata, but schema additions do not prove that a remote executor, dataset, model, or artifact is available.
- True WARDEN execution, Probe/model validation, and real study HTTP smoke are **NOT_RUN**. The Research Workbench reports capability responses and registered metadata; it does not represent a Study registration as a run.
- Public defense execute operations remain blocked in the App until an executor, permission contract, and real result are validated.
- Public artifact content routes are not exposed through an App-controlled download and integrity-verification flow.
- Public Probe train/predict operations are not exposed through an App Probe/SAE workflow.
- No Loop-scoped cancel operation is published (`POST /v1/investigation-loops/{loop_id}/cancel`); workflow/run cancellation routes use different resource identities and are not mapped by the App.
- The presence of a route in OpenAPI does not prove runtime resources or WARDEN Live Gate readiness.

## Response and security invariants

- General API authentication uses `X-AgentGuard-Token`; operator routes use `X-AgentGuard-Operator-Token`.
- Error responses use the declared upstream HTTP status and typed error code. The BFF sanitizes upstream messages before returning them to browser clients.
- Paginated investigation, report, loop, and strategy-evaluation lists preserve upstream `limit`/`offset` semantics. Loop listing follows `next_offset`; strategy-evaluation listing is consumed with bounded paging.
- Investigation, Loop and Study POST requests are never automatically retried by the HTTP client. Loop ambiguity uses its persisted reconciliation flow; Study ambiguity is recoverable only by an explicit same-body/same-key request under the RC5 upstream idempotency contract.
- Evidence levels remain source-provided. Unknown or missing levels are displayed as unknown; observational evidence is not promoted to causal confirmation.

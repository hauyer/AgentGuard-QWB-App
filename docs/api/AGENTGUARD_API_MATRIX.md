# AgentGuard API Matrix

**Pinned runtime:** `9a8ee1f5e78a0b254c17ea66ac5b140aa7e1e89a` (`1.1.0rc3`)
**OpenAPI source:** `9a8ee1f5e78a0b254c17ea66ac5b140aa7e1e89a`; `86` paths and `98` operations.
**Verification:** static source comparison only; live HTTP smoke, identity, and readiness are **NOT_RUN**. RC2→RC3 changes only `info.version`; see [RC3 OpenAPI diff](AGENTGUARD_OPENAPI_DIFF_RC3.md), the [historical RC2 diff](AGENTGUARD_OPENAPI_DIFF_RC2.md), and the machine-readable [version contract](../../contracts/agentguard-version.json).

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

## Unexposed or blocked capabilities

- New in rc2 and not integrated: `GET /v1/system/identity`, `POST /v1/investigation-loops/{loop_id}/reconcile`. Both remain candidate operations until live behavior is verified.
- Published but not exposed by the App: `POST/GET /v1/studies`, Study detail/integrity/analysis routes, run-scoped `GET/POST /v1/runs/{run_id}/experiments/paired`, and `POST /v1/runs/{run_id}/interventions`.
- Study registry routes are **STATIC_ONLY**: live service behavior and project ownership are unverified, Study creation has no upstream idempotency header, and the schema does not contain the requested track/Arm matrix. Analysis accepts caller-supplied outcome arrays; source refs and hashes are not independent provenance proof.
- Run-scoped paired/intervention routes are **BLOCKED** for real study execution. They require an existing run/design/action and do not map to Study/Arm records; the production AgentGuard API refuses a real paired run without a validated executor. WARDEN Live Gate remains **BLOCKED**.
- RC3 exports paired-experiment and evidence JSON Schemas, but schema additions do not prove that a remote executor, dataset, model, or artifact is available.
- True WARDEN execution, Probe/model validation, and real study HTTP smoke are **NOT_RUN**. The Experiments page's gate notice is informational and does not represent a Study record.
- Public defense execute operations remain blocked in the App until an executor, permission contract, and real result are validated.
- Public artifact content routes are not exposed through an App-controlled download and integrity-verification flow.
- Public Probe train/predict operations are not exposed through an App Probe/SAE workflow.
- No Loop-scoped cancel operation is published (`POST /v1/investigation-loops/{loop_id}/cancel`); workflow/run cancellation routes use different resource identities and are not mapped by the App.
- The presence of a route in OpenAPI does not prove runtime resources or WARDEN Live Gate readiness.

## Response and security invariants

- General API authentication uses `X-AgentGuard-Token`; operator routes use `X-AgentGuard-Operator-Token`.
- Error responses use the declared upstream HTTP status and typed error code. The BFF sanitizes upstream messages before returning them to browser clients.
- Paginated investigation, report, loop, and strategy-evaluation lists preserve upstream `limit`/`offset` semantics. Loop listing follows `next_offset`; strategy-evaluation listing is consumed with bounded paging.
- Investigation and Loop POST requests are never automatically retried by the BFF. Ambiguous results use persisted request identity and read-only reconciliation.
- Evidence levels remain source-provided. Unknown or missing levels are displayed as unknown; observational evidence is not promoted to causal confirmation.

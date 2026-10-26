# AgentGuard API Matrix

**Pinned runtime:** `63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc` (`1.1.0rc2`)
**OpenAPI source:** `63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc`; `86` paths.
**Verification:** static source comparison only; live HTTP smoke is **NOT_RUN**. See [RC2 OpenAPI diff](AGENTGUARD_OPENAPI_DIFF_RC2.md) and the machine-readable [version contract](../../contracts/agentguard-version.json).

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

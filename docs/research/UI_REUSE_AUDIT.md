# UI / BFF Reuse Audit

> The original inventory below describes the RC3 planning point. The current RC5 implementation and revised reuse decisions are recorded in the addendum at the end.

Date: 2026-10-28
Repository: `hauyer/AgentGuard-QWB-App`
Starting point: `feature/b25-b33-real-integration` @ `74627b234a86ef13615e90346e0c8f3a3c86fc7e`
Scope: this App repository only. AgentGuard, WARDEN, StegoPot, and FRACTAL-Bench remain read-only.

## Existing assets and extension points

| Area | Existing implementation and callers | Reuse/extension decision |
| --- | --- | --- |
| AgentGuard contract | `contracts/agentguard-version.json`; `scripts/check_agentguard_contract.py`; `integration-data/agentguard-openapi-63fe1b5.json`; `integration-data/agentguard-openapi-8a7c154.json`; `docs/api/AGENTGUARD_API_MATRIX.md`; RC2/RC1 diff notes | Retain prior snapshots and make the checker enforce the RC2→RC3 delta, existing 33-operation request/response/security invariants, raw/canonical hashes, source pin, and explicit unsupported study routes. Add a rollback note. |
| Shared upstream client | `backend/app/integrations/agentguard_client.py`, used by API routes and services for health, readiness, discovery, investigations, loops, evidence, experiments, reports, and strategy-evaluation reads | Continue using this single fixed-base-URL client and its existing server-side credentials, bounded response handling, transport protections, and error sanitization. Do not add another client or accept a caller-provided URL. |
| Experiment listing and comparison | `backend/app/api/routes/experiments.py` → `backend/app/services/reports_service.py` → `AgentGuardClient`; `frontend/src/pages/ExperimentsPage.tsx` → `frontend/src/hooks/use-reports.ts` → existing report services | Keep the existing experiment table/comparison panel as the study-workbench host. The upstream OpenAPI does publish generic Study preregistration/list/detail/integrity/analysis operations and run-scoped paired/intervention operations, but the App does not currently expose them. Show the exact static/live gate; do not add fake Study rows, arms, metrics, or execution buttons. |
| Persisted research evaluations | `backend/app/api/routes/strategy_evaluations.py` checks live reachability, admin scope, and discovered published list/detail operations before reading; frontend `StrategyComparisonPage.tsx`, `frontend/src/services/research.ts`, and research hooks render persisted evaluation DTOs | Preserve source-provided values and nulls. This is a read-only strategy-evaluation resource, not a Study registration or four-layer intervention API. Do not reinterpret it as one. |
| System readiness and status | `backend/app/api/routes/system.py` and `backend/app/services/status_service.py`; `frontend/src/pages/SystemOverviewPage.tsx`; dashboard/status hooks and shared layer-status cards | Reuse its separate AgentGuard, WARDEN, model runtime, Probe/SAE, threat-contract, artifact, and feature statuses. Health is not research readiness. New status text must preserve `blocked`, `unsupported`, `unavailable`, `unknown`, and `not run` as distinct states. |
| Evidence and graph | `backend/app/api/routes/evidence.py`, `backend/app/api/routes/graph.py`; `backend/app/services/evidence_service.py`, `graph_service.py`; `EvidencePage.tsx`, `InteractionGraphPage.tsx`; shared source/evidence/verification badges | Extend only for published, authorized upstream fields. Existing evidence views show artifact references as metadata and do not open local file URIs. Do not construct causal edges or expose artifact contents without a published route and controlled download verification. |
| Investigations and loops | `backend/app/api/routes/investigations.py`, `loop_creation.py`; services for project authorization, idempotent submission, reconciliation, and ownership; investigation workspace/detail/journal pages and `use-investigation-loops` | Keep investigation and Loop identity separate from any future Study identity. Reuse current project authorization and durable submission patterns only if a formal Study contract is later published; do not reuse Loop idempotency keys or its state machine for studies. |
| Project/RBAC/audit | `backend/app/services/project_service.py`, `resource_access.py`, `backend/app/api/deps.py`; `backend/app/api/routes/projects.py` and `audit.py`; `Project`, `ProjectMember`, `ProjectInvestigation`, `ProjectInvestigationLoop`, and `AppAuditEvent` in `backend/app/models/app.py` | Continue failing closed on missing or ambiguous project ownership. Existing Live experiment and strategy-index routes are admin-scoped where upstream ownership is global/unknown. Do not broaden roles or create a parallel research database. |
| Report DTO and exports | Report assembly and JSON/PDF export routes in `backend/app/api/routes/experiments.py`; `backend/app/services/reports_service.py`; `frontend/src/pages/ReportsPage.tsx`, `MultiRoundReportPage.tsx`, and `frontend/src/services/reports.ts` | Preserve one source-backed report object for display and export, existing authorization and export audit. No four-layer report sections can be populated until upstream provides real study/arm/artifact data; do not generate prose or causal conclusions in the App. |
| Shared UI and verification | `PageHeader`, `Card`, `Badge`, `DemoBanner`, `ErrorState`, source/evidence/verification badges; existing page-level Vitest and Playwright suites; backend pytest and Docker checks | Reuse the existing components, empty/error states, test conventions, and current routes. No `ExperimentsPageV2`, second navigation tree, second client, or research lifecycle table is planned for this static-only integration. |

## Current upstream capability boundary

The RC2 App contract contains 86 OpenAPI paths and the App consumes 33 operations. The reviewed RC3 candidate changes the OpenAPI version from `1.1.0rc2` to `1.1.0rc3` while retaining the same 86 paths and operation/schema contracts. The pinned OpenAPI does publish `POST/GET /v1/studies`, Study detail/integrity/analysis operations, `GET/POST /v1/runs/{run_id}/experiments/paired`, and `POST /v1/runs/{run_id}/interventions`. The preregistration schema does not define the requested track/arm matrix; paired and intervention routes are tied to an existing run. The upstream WARDEN Live Gate is `BLOCKED`; true WARDEN execution and real model validation remain `NOT_RUN`.

The Study API source stores preregistrations in AgentGuard's own local registry. `POST /v1/studies` has no declared idempotency header and creates a new registry entry on each call. Its analysis endpoint accepts caller-supplied outcome arrays; artifact references and hashes are metadata, not independent provenance proof. The paired route requires an explicit executor for real backends, while the production API factory rejects direct executor injection. Therefore these routes are valid static contracts, but they are not safe to expose as live App Study/Arm workflows without service verification, project ownership mapping, and a safe submission/reconciliation contract.

Consequences for this App change:

- A static RC3 pin may be recorded as `STATIC_ONLY`; it does not enable Study/Arm writes or claim a deployed service is RC3.
- The existing strategy-evaluation API remains a persisted read model and cannot stand in for Study/Arm data.
- The Experiments page explains that Study API schemas exist statically but are not live-verified or App-authorized; four-layer execution remains `BLOCKED`. It must not render synthetic success cards, zero-filled metrics, or causal claims.
- Existing JSON/PDF reports remain based on their current authorized sources. Four-layer reports and artifact downloads wait for a published, authorized upstream contract and real source data.
- HTTP smoke and real App→AgentGuard→WARDEN execution cannot be marked passed without a target service, credentials, and auditable runtime evidence.

## Planned App-only change set

1. Preserve the current 33-operation baseline and RC1/RC2 snapshots; add the exact RC3 snapshot and a machine-checked, narrow RC2→RC3 diff.
2. Record runtime commit, API-source commit, upstream CI, raw/canonical snapshot hashes, static-only method, and live-smoke status as separate fields in the version contract and release/API documentation.
3. Add APP-0 through APP-5 gate records. Mark work dependent on absent upstream Study APIs or the blocked WARDEN gate explicitly `BLOCKED`, and live HTTP checks `NOT_RUN`.
4. Reuse the existing Experiment/System Status UI for an honest capability explanation. Keep current project/RBAC/CSRF/audit/report behavior intact; do not expose the published Study and run-scoped intervention candidates until project authorization, submission safety, and live-service behavior are verified.
5. Extend contract and UI tests to reject unsupported Study routes and to preserve unknown/null and blocked/not-run status semantics. Run the existing verification pipeline after edits.

## Rollback

Restore `contracts/agentguard-version.json` to its prior RC2 pin (`63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc`) and select its retained `integration-data/agentguard-openapi-63fe1b5.json` snapshot. Keep the RC3 snapshot and diff report in history for audit. No database migration or runtime state transition is planned for this static-only upgrade.

## RC5 implementation addendum — 2026-10-28

- Contract reuse: the single AgentGuard client remains the only upstream HTTP path. It now pins RC5, exposes the capability/Study client methods, validates RC5 `Idempotency-Key`, and still never retries POST automatically.
- BFF reuse: existing `require_role_csrf`, `require_project_access`, SQLAlchemy/Alembic, app audit service, and error sanitization are used. Migration 0009 stores only the App's project association and submission intent/response snapshot; AgentGuard remains authoritative for Study content.
- Study privacy: global upstream list is not proxied. The App lists its own project mapping; detail, integrity and analyses first require that mapping. The mapping uses a globally unique upstream study ID to prevent association with multiple projects.
- UI reuse: the existing Router, AppLayout, `PageHeader`, `Card`, `Badge`, error/empty state, TanStack Query and API service are extended. The new Research Workbench binds queries and mutations to a selected project and visibly distinguishes recorded project rows, synthetic upstream mode, live capability response and unavailable data.
- Reporting/execution boundary: existing report DTO/export remain unchanged. No analysis write, intervention execution, Probe/SAE workflow or artifact content downloader is added. RC5 `measured` analysis and WARDEN execution remain blocked pending verified source artifacts and real execution evidence.
- Verification boundaries: deterministic Stub tests verify flow behavior, not live AgentGuard. Real HTTP Smoke and WARDEN execution remain **NOT_RUN** / **BLOCKED**.

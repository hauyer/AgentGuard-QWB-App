# APP-2 — Controlled Study BFF

**Status:** RC5 static integration PASS; live-service acceptance remains BLOCKED / NOT_RUN.

> Historical RC3 assessment follows. Its statements that no Study BFF or project mapping existed are superseded by the RC5 update at the end of this file.

## Reused controls

- Existing integration remains in `backend/app/integrations/agentguard_client.py`, with a fixed server-side base URL and credentials, 4 MiB response limit, `trust_env=False`, redirects disabled, error-body sanitization, and GET-only retry behavior.
- Existing role, CSRF, project ownership, resource-access, audit, and persisted ambiguous Loop-submission patterns remain intact.
- Study and paired operations are declared in OpenAPI, but the Study list is global and has only `limit`; upstream `POST /v1/studies` has no idempotency header and appends a new entry per call. The App has no Study-to-project mapping.
- Study analysis accepts caller-supplied outcome arrays and treats references/hashes as metadata. The App cannot present these results as provenance-verified research.
- Run-scoped paired execution requires an existing run/design/action. A real backend without a validated `paired_executor` returns `PAIRED_REPLAY_UNAVAILABLE`; the production API factory rejects direct executor injection.

## Gate decision

The App does not proxy these operations until a real service verifies the exact deployed contract and the App has a project-scoped ownership mapping plus safe create/reconcile semantics. No blind POST retry, cross-project list/detail, second client, or second research database has been introduced. This gate is not complete for live Study use; its unresolved dependency is explicit rather than represented as a successful integration.

## Validation and rollback

The RC3 offline snapshot checker and its contract tests verify that candidate operations are published and remain outside `supported_endpoints`. Existing backend authorization tests remain part of APP-5. Rollback is to the RC2 pin; no schema migration was made in this historical gate.

## RC5 update — 2026-10-28

- Pin: runtime/API source `d85aa97e1566e2c50816f2ade3129235266ec704`, OpenAPI `1.1.0rc5`; current upstream branch head is documentation-only `c67c7f1f186aeec6d95d6a6c1c0a48bb1a84ea38`.
- Added `project_study_submissions` migration 0009 for the project mapping, hashed idempotency key, normalized request/fingerprint, source pin, response snapshot, status and request identity. A Study ID is unique across projects; keys are scoped by project and actor.
- Added `/api/research/capabilities`, project-scoped Study list/register/detail/integrity/analysis-list routes. Each read checks project access and local Study mapping before making upstream detail requests. The project list never queries or returns the upstream global index.
- Registration intent commits before POST. The BFF requires a key, derives the upstream RC5 key without storing the user's key in clear text, and the HTTP client never retries POST. A repeated identical request is an explicit caller retry; a changed body with the same key returns 409. Ambiguous or in-flight records survive process restart.
- Stub tests cover registration and duplicate handling, cross-project visibility, synthetic source labeling, and explicit recovery after a simulated lost response.
- Real AgentGuard HTTP behavior and credential authorization remain **NOT_RUN**. WARDEN execution and artifact provenance remain **BLOCKED**; analysis writes are not exposed.

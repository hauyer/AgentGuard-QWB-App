# APP-2 — Controlled Study BFF

**Status:** BLOCKED pending live-service and ownership evidence. No Study BFF routes were added.

## Reused controls

- Existing integration remains in `backend/app/integrations/agentguard_client.py`, with a fixed server-side base URL and credentials, 4 MiB response limit, `trust_env=False`, redirects disabled, error-body sanitization, and GET-only retry behavior.
- Existing role, CSRF, project ownership, resource-access, audit, and persisted ambiguous Loop-submission patterns remain intact.
- Study and paired operations are declared in OpenAPI, but the Study list is global and has only `limit`; upstream `POST /v1/studies` has no idempotency header and appends a new entry per call. The App has no Study-to-project mapping.
- Study analysis accepts caller-supplied outcome arrays and treats references/hashes as metadata. The App cannot present these results as provenance-verified research.
- Run-scoped paired execution requires an existing run/design/action. A real backend without a validated `paired_executor` returns `PAIRED_REPLAY_UNAVAILABLE`; the production API factory rejects direct executor injection.

## Gate decision

The App does not proxy these operations until a real service verifies the exact deployed contract and the App has a project-scoped ownership mapping plus safe create/reconcile semantics. No blind POST retry, cross-project list/detail, second client, or second research database has been introduced. This gate is not complete for live Study use; its unresolved dependency is explicit rather than represented as a successful integration.

## Validation and rollback

The RC3 offline snapshot checker and its contract tests verify that candidate operations are published and remain outside `supported_endpoints`. Existing backend authorization tests remain part of APP-5. Rollback is to the RC2 pin; no schema migration was made in this gate.

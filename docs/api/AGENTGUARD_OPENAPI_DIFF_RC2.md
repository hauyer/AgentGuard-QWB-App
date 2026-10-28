# AgentGuard OpenAPI comparison: 1.1.0rc1 to 1.1.0rc2

**Verified:** 2026-10-26  
**Method:** static source review; no running AgentGuard service was configured.

## Fixed sources

| Item | Previous pin | Candidate pin |
| --- | --- | --- |
| Runtime commit | `8a7c154116ca48c80e2dbf5291e1ff70f5dbdd25` | `63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc` |
| API snapshot source commit | `66dae883fb75cf90ef735b94d2f5c9b565ba5ad3` | `63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc` |
| API version | `1.1.0rc1` | `1.1.0rc2` |
| OpenAPI paths | 84 | 86 |
| Raw snapshot SHA-256 | `d577e6001883ada17d47f195cafe48c5394e46c5f16f587636eb907a1e1aa78e` | `2ce83660a67111a346a2de9772fcaec1938a4a5de713439de34a83e372b9a5e5` |
| Canonical JSON SHA-256 | `e2d6d9bd7cf94441fa508b34af922b8da7cf724778ff62d10b728367a93c3c9f` | `430a8115f4dfb8c865060d45345a58bf267f60657b1ba8ab1c0faa2ba3acf41c` |

These canonical digests are the values emitted by the App's historical serializer (`json.dumps(sort_keys=True)` with default separators and ASCII escaping). RC3 standardized the contract checker on AgentGuard's identity algorithm (sorted keys, compact separators, unescaped Unicode, UTF-8). Under that algorithm the same unchanged RC1/RC2 raw snapshots hash to `cf6967dc0a0bb1757193e64a92e2612dd095e203b290db006f3c97a5f5fa3ecc` and `d0a04af3d87c9dca3b30aa7feed89f84447103ed9e8c32c063257c8214a25834`. The raw snapshot bytes were not changed by this canonicalization update.

The candidate runtime commit has a successful [AgentGuard CI run 40314646080](https://github.com/hauyer/AgentGuard/actions/runs/40314646080) with Python 3.11, 3.12, and 3.13 jobs passing. This confirms the upstream commit's CI result; it does not validate a running service or WARDEN execution.

## Operation and schema diff

- Operations: 96 → 98.
- Added: `GET /v1/system/identity`, `POST /v1/investigation-loops/{loop_id}/reconcile`.
- Removed: none.
- Added component schemas: `SystemIdentityResponse`, `InvestigationLoopReconciliationResponse`, `ReconciledWorkflowView`.
- Removed component schemas: none.
- All 33 App-supported operations retain the same OpenAPI `parameters`, `requestBody`, `responses`, and `security` definitions. The offline checker compares these fields against the retained rc1 snapshot on every run.
- Existing Loop idempotency and pagination definitions, request validation, error response schemas, and evidence-level names do not change for the App-supported operations.

## New operations and release boundary

`GET /v1/system/identity` reports declared build identity and a canonical hash of the runtime's OpenAPI contract. The response has not been checked against a running service and is not consumed by the App.

`POST /v1/investigation-loops/{loop_id}/reconcile` is documented in the candidate source as query-only: it may recover known upstream workflow identity or persisted local reports; it does not re-submit a WARDEN plan or run. An unproven result remains blocked and requires reconciliation. The endpoint has not been live-tested and is not consumed by the App.

Both operations remain candidates. They are absent from `supported_endpoints`, the BFF client, and the production UI until their live behavior is verified. Public OpenAPI operations for defense execution, artifacts, and Probe train/predict also remain outside the App's supported contract: published schemas alone are not evidence of a verified executor, controlled artifact integrity flow, or live Probe/SAE result. Defense execution remains blocked in the App.

RC2 has no `POST /v1/investigation-loops/{loop_id}/cancel` operation. It does publish cancellation operations for kernel workflows and runs, but the App does not map those identities to a Loop cancel operation or claim that cancellation was verified.

## Validation status

- **PASS — static source comparison:** candidate snapshot at `63fe1b5662df93fbf06750ecf09c14ee9e6bd5cc` matches the pinned hashes and the declared 84→86 path / 96→98 operation delta.
- **PASS — App contract compatibility:** the 33 supported operation definitions are unchanged across the two snapshots.
- **NOT_RUN — live OpenAPI and HTTP smoke:** no AgentGuard service or credentials were configured or reachable.
- **BLOCKED — WARDEN Live Gate:** no real WARDEN execution was validated. Stub, fixture, and offline results do not change this state.

The previous rc1 snapshot remains checked in at `integration-data/agentguard-openapi-cd3e9f3.json`; the current rc2 snapshot is `integration-data/agentguard-openapi-63fe1b5.json`.

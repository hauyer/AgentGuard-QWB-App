# APP-4 — Report and audit boundary

**Status:** Existing reports preserved; four-layer research reporting is BLOCKED pending verified upstream source data.

> This record was written before RC5 Study mapping was added. The report boundary below remains current; its old statement that no project mapping existed is historical.

## Reused controls

- The existing report assembly and JSON/PDF exports continue to use the same report object and authorized source reads in `backend/app/api/routes/experiments.py` and `backend/app/services/reports_service.py`.
- Existing project/report access checks and export audit events remain unchanged.
- Evidence remains source-labeled. Unknown values stay unknown; local `file://` references are not opened; export does not infer causal effects.

## Historical gate decision

The Study analysis endpoint consumes caller-provided paired arrays and says its artifact references/hashes are not independent proof of provenance. The paired-execution gate remains blocked, and there is no project-authorized Study/Arm association. Adding a four-layer report section would therefore imply data the App cannot verify. No new report fields, generated findings, or artifact-download routes were added. The requested Study report sections, family counts, confidence intervals, and causal gates remain unimplemented until verified upstream reports exist.

## Validation and rollback

Existing report JSON/PDF and authorization tests remain included in APP-5. This historical gate changed no report DTO. Rollback is unnecessary beyond reverting APP-1/APP-3 documentation and status work.

## RC5 update — 2026-10-28

Project-owned Study metadata and response snapshots are now stored by migration 0009. The existing reports service still does not invent Study/Arm metrics or causal results. Study analysis writes remain unexposed because caller-provided values and artifact references do not independently verify content; RC5 measured analysis remains blocked until real WARDEN artifacts are verified. Report sections for pair/family outcomes, confidence intervals, adjusted p-values and artifact provenance remain unavailable until AgentGuard returns verifiable source-backed data. Existing JSON/PDF output remains unchanged.

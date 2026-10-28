# APP-4 — Report and audit boundary

**Status:** Existing reports preserved; four-layer research reporting is BLOCKED pending verified upstream source data.

## Reused controls

- The existing report assembly and JSON/PDF exports continue to use the same report object and authorized source reads in `backend/app/api/routes/experiments.py` and `backend/app/services/reports_service.py`.
- Existing project/report access checks and export audit events remain unchanged.
- Evidence remains source-labeled. Unknown values stay unknown; local `file://` references are not opened; export does not infer causal effects.

## Gate decision

The Study analysis endpoint consumes caller-provided paired arrays and says its artifact references/hashes are not independent proof of provenance. The paired-execution gate remains blocked, and there is no project-authorized Study/Arm association. Adding a four-layer report section would therefore imply data the App cannot verify. No new report fields, generated findings, or artifact-download routes were added. The requested Study report sections, family counts, confidence intervals, and causal gates remain unimplemented until verified upstream reports exist.

## Validation and rollback

Existing report JSON/PDF and authorization tests remain included in APP-5. This gate changes no report DTO, audit schema, or database state; rollback is unnecessary beyond reverting APP-1/APP-3 documentation and status work.

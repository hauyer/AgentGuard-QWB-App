/** Evidence and defense workspace types (B5). */

import type { MetaInfo } from "./dashboard";

export interface CausalValidation {
  method?: string | null;
  status?: string | null;
  note?: string | null;
}

export interface EvidenceItem {
  evidence_id: string;
  source_system?: string | null;
  warden_run_id?: string | null;
  warden_plan_id?: string | null;
  target_type?: string | null;
  target_ref?: string | null;
  scenario_id?: string | null;
  artifact_refs: string[];
  evidence_type?: string | null;
  evidence_level: string;
  risk_type?: string | null;
  confidence?: number | null;
  limitations: string[];
  verification_status: string;
  run_status?: string | null;
  model_version?: string | null;
  causal_validation?: CausalValidation | null;
  hypothesis?: string | null;
}

export interface EvidenceResponse {
  meta: MetaInfo;
  evidence: {
    request_id?: string | null;
    workflow_status?: string | null;
    run_status?: string | null;
    limitations: string[];
    items: EvidenceItem[];
  };
}

export interface DefenseCandidate {
  candidate_id: string;
  risk?: string | null;
  target?: string | null;
  operation_type?: string | null;
  rationale?: string | null;
  authorization_required?: string | null;
  estimated_cost?: { tokens?: number | null; time_seconds?: number | null } | null;
  related_evidence: string[];
  status?: string | null;
  execution_supported: boolean;
  execution_reason?: string | null;
}

export interface DefenseResponse {
  meta: MetaInfo;
  defense: {
    run_id?: string | null;
    status?: string | null;
    candidates: DefenseCandidate[];
    policy_notes: string[];
    execution_performed: boolean;
    evidence_mode?: string | null;
  };
}

export interface HistoricalOutcome {
  outcome_id: string;
  policy?: string | null;
  operation_type?: string | null;
  status?: string | null;
  verified_at?: string | null;
  source?: string | null;
  note?: string | null;
}

export interface DefenseOutcomesResponse {
  meta: MetaInfo;
  outcomes: HistoricalOutcome[];
}

/** Experiment comparison, report and experience types (B6). */

import type { MetaInfo } from "./dashboard";

export interface Experiment {
  experiment_id: string;
  run_id?: string | null;
  request_id?: string | null;
  scenario_id?: string | null;
  model_version?: string | null;
  investigation_strategy?: string | null;
  defense_strategy?: string | null;
  execution_status?: string | null;
  risk_indicators?: Record<string, number> | null;
  utility?: { normal_task_success_rate?: number | null } | null;
  budget?: { tokens?: number | null; cost_usd?: number | null; time_seconds?: number | null } | null;
  result_source?: string | null;
  created_at?: string | null;
}

export interface ExperimentsResponse {
  meta: MetaInfo;
  items: Experiment[];
}

export interface ReportFinding {
  finding_id: string;
  risk_type?: string | null;
  summary?: string | null;
  evidence_ids: string[];
  severity?: string | null;
}

export interface Report {
  run_id?: string | null;
  request_id?: string | null;
  experiment_id?: string | null;
  scenario_id?: string | null;
  status?: string | null;
  policy_profile?: string | null;
  created_at?: string | null;
  findings: ReportFinding[];
  intervention_history?: Array<Record<string, unknown>> | null;
  evidence: Array<{ evidence_id?: string | null; evidence_level?: string | null; verification_status?: string | null }>;
  defense_candidates: Array<{ candidate_id?: string | null; status?: string | null; execution_supported?: boolean | null }>;
  limitations: string[];
  source_note?: string | null;
}

export interface ReportResponse {
  meta: MetaInfo;
  report: Report;
}

export interface InvestigationLoopReport {
  schema_version: string;
  data_mode: "live";
  generated_at: string;
  project: Record<string, unknown>;
  investigation: Record<string, unknown>;
  loop: Record<string, unknown>;
  risk_analysis: { available: boolean; data: Record<string, unknown> | null; error_code: string | null };
  decisions: Record<string, unknown> & { items: Array<Record<string, unknown>> };
  evidence_changes: Record<string, unknown> & { items: Array<Record<string, unknown>> };
  budget: Record<string, unknown>;
  defense: { available: boolean; data: Record<string, unknown> | null; error_code: string | null };
  strategy_evaluation: Record<string, unknown> | null;
  strategy_evaluation_note: string;
  data_sources: Array<{ name: string; source: string; available: boolean }>;
  limitations: string[];
}

export interface InvestigationLoopReportResponse {
  meta: MetaInfo;
  report: InvestigationLoopReport;
}

export interface Experience {
  experience_id: string;
  scenario_id?: string | null;
  risk_type?: string | null;
  title?: string | null;
  action?: string | null;
  verification_level?: string | null;
  recommendation_allowed?: boolean | null;
  policy_version?: string | null;
  evidence_refs: string[];
  validation_notes?: string | null;
  audit_run_id?: string | null;
  applicable_scenarios: string[];
  created_at?: string | null;
}

export interface ExperiencesResponse {
  meta: MetaInfo;
  items: Experience[];
  total?: number | null;
  recommendation_note?: string | null;
}

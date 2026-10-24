/** Investigation workflow types (B3), mirroring the BFF contracts. */

import type { MetaInfo } from "./dashboard";

export type AuditMode = "observation" | "capture_only" | "detection" | "causal_audit" | "defense_evaluation";

export interface CaptureTarget {
  target_id: string;
  agent_ids: string[];
  module?: string | null;
  layer?: string | null;
  component?: string | null;
  token_policy?: string | null;
  retain_gradient: boolean;
}

export interface CreateInvestigationRequest {
  contract_id: string;
  model_id: string;
  runtime_id: string;
  mode: AuditMode;
  probe_id?: string | null;
  sae_id?: string | null;
  capture_targets: CaptureTarget[];
  metadata: Record<string, unknown>;
  authorization_ref?: string | null;
  scenario_id?: string | null;
  risk_type?: string | null;
  start_run: boolean;
  wait_for_completion: boolean;
  timeout_seconds: number;
  poll_interval_seconds: number;
}

export type InvestigationStatus = "pending" | "planned" | "running" | "completed" | "blocked" | "failed";

export interface InvestigationSummaryRow {
  request_id: string;
  scenario_id?: string | null;
  mode?: string | null;
  status: InvestigationStatus;
  workflow_status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  plan_id?: string | null;
  run_id?: string | null;
  experiment_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  demo_note?: string | null;
}

export interface InvestigationListResponse {
  meta: MetaInfo;
  items: InvestigationSummaryRow[];
  count: number;
  offset: number;
  limit: number;
  total: number;
  next_offset: number | null;
}

export interface InvestigationDetail {
  request_id: string;
  contract_id?: string | null;
  model_id?: string | null;
  runtime_id?: string | null;
  mode?: string | null;
  scenario_id?: string | null;
  risk_type?: string | null;
  status: InvestigationStatus;
  workflow_status?: string | null;
  revision?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
  plan_id?: string | null;
  run_id?: string | null;
  experiment_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  result?: unknown;
  follow_up?: string[] | null;
  allows_defense_candidates?: boolean | null;
  demo_note?: string | null;
}

export interface TimelineEvent {
  step: string;
  label: string;
  status: "completed" | "running" | "pending" | "blocked" | "failed";
  at?: string | null;
  detail?: string;
}

export interface TimelineResponse {
  meta: MetaInfo;
  events: TimelineEvent[];
}

export interface Scenario {
  scenario_id: string;
  name: string;
  description?: string | null;
  threat_models?: string[] | null;
  risk_types?: string[] | null;
}

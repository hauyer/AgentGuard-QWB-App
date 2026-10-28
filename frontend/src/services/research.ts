import { apiGet, apiPost } from "./api";

export type StrategyName = "fixed_order" | "risk_score" | "information_value" | "experience" | "llm";
export type DataPartition = "training" | "validation" | "test" | "held_out_family";

export interface StrategyEvaluationIndexItem {
  evaluation_id: string;
  comparison_id: string;
  report_artifact_id: string;
  data_partition: DataPartition;
  source_commit: string | null;
  executed_at: string;
  status: string;
}

export interface StrategyEvaluationListResponse {
  meta: { data_mode: string; capability: string; source_note: string };
  schema_version: string;
  items: StrategyEvaluationIndexItem[];
  count: number;
  offset: number;
  limit: number;
}

export interface StrategyEvaluationRun {
  experiment_id: string;
  run_label: string;
  strategy: StrategyName;
  repetition: number;
  base_request_id: string;
  execution_status: string;
  stop_reason: string | null;
  rounds_executed: number;
  steps_to_first_evidence: number | null;
  effective_action_ratio: number | null;
  blocked_ratio: number | null;
  unsupported_ratio: number | null;
  redundant_action_count: number;
  evidence_refs_collected: number;
  hypotheses_raised: number;
  model_calls_used: number;
  elapsed_seconds: number;
  strategy_degraded: boolean;
  limitations: string[];
}

export interface StrategyAggregate {
  strategy: StrategyName;
  repetitions: number;
  completed_runs: number;
  blocked_runs: number;
  mean_rounds: number | null;
  mean_steps_to_first_evidence: number | null;
  mean_effective_action_ratio: number | null;
  mean_redundant_actions: number | null;
  mean_evidence_refs: number | null;
  mean_elapsed_seconds: number | null;
  degradation_rate: number | null;
  notes: string[];
}

export interface StrategyEvaluation {
  schema_version: string;
  comparison_id: string;
  base_request_ids: string[];
  strategies: StrategyName[];
  repetitions: number;
  data_partition: DataPartition;
  runs: StrategyEvaluationRun[];
  aggregates: StrategyAggregate[];
  risk_identification_metrics: null;
  defense_effectiveness_metrics: null;
  limitations: string[];
  source_commit: string | null;
  executed_at: string;
  report_artifact_id: string | null;
}

export interface StrategyEvaluationDetailResponse {
  meta: { data_mode: string; capability: string; source_note: string };
  evaluation: StrategyEvaluation;
}

export type ResearchCapabilityStatus =
  | "SUPPORTED_AND_READY"
  | "SUPPORTED_BUT_BLOCKED"
  | "UNSUPPORTED"
  | "UNAVAILABLE"
  | "UNKNOWN";

export interface ResearchCapability {
  capability: string;
  status: ResearchCapabilityStatus;
  blockers: string[];
  source_version: string | null;
  source_api_version: string | null;
  advertised_by_warden: boolean | null;
  observed_at: string;
  evidence_refs: string[];
  operation_id: string | null;
  contract_ref: string | null;
}

export interface ResearchCapabilitiesResponse {
  meta: { data_mode: string; agentguard_commit: string; source_note: string };
  report: {
    schema_version: string;
    backend_status: string;
    source: string;
    source_version: string | null;
    source_api_version: string | null;
    observed_at: string;
    capabilities: ResearchCapability[];
    limitations: string[];
  };
}

export interface ProjectStudyRecord {
  study_id: string | null;
  title: string;
  track: string | null;
  status: string;
  study: Record<string, unknown> | null;
  registration_sha256: string | null;
  request_id: string;
  source: {
    mode: string;
    origin_mode: string;
    agentguard_commit: string;
    created_at: string | null;
  };
  error_code: string | null;
  error_message: string | null;
}

export interface ProjectStudiesResponse {
  meta: { data_mode: string; source_note: string };
  items: ProjectStudyRecord[];
  count: number;
  total: number;
  limit: number;
  offset: number;
  next_offset: number | null;
}

export interface StudyRegistrationPayload {
  schema_version: "0.1";
  title: string;
  research_question: string;
  primary_hypothesis: string;
  primary_outcome: string;
  primary_direction: "increase" | "decrease" | "two_sided";
  secondary_outcomes?: string[];
  analysis_method?: "paired" | "clustered_paired";
  multiplicity_method?: "none" | "holm" | "benjamini_hochberg";
  alpha?: number;
  planned_pairs: number;
  planned_case_families: number;
  seed?: number;
  matching_variables: string[];
  inclusion_criteria: string[];
  exclusion_criteria?: string[];
  stopping_rule: string;
  missing_data_rule: string;
  deviations_policy?: string;
  protocol_version?: string;
  code_revision?: string;
  track?: "mechanism_testbed" | "live_steganography";
  arms?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface StudySubmissionResponse {
  submission: ProjectStudyRecord;
  replayed: boolean;
  message?: string;
}

export interface StudyDetailResponse {
  meta: { data_mode: string; agentguard_commit: string; source_note: string };
  study: Record<string, unknown>;
  project_registration: ProjectStudyRecord;
}

export interface StudyIntegrityResponse {
  meta: { data_mode: string; agentguard_commit: string };
  integrity: Record<string, unknown>;
}

export interface StudyAnalysesResponse {
  meta: { data_mode: string; agentguard_commit: string; source_note: string };
  items: Array<Record<string, unknown>>;
  count?: number;
  total?: number;
  offset?: number;
  limit?: number;
  next_offset?: number | null;
}

export function fetchStrategyEvaluations(signal?: AbortSignal): Promise<StrategyEvaluationListResponse> {
  return apiGet<StrategyEvaluationListResponse>("/research/strategy-evaluations?limit=500", signal);
}

export function fetchStrategyEvaluation(
  evaluationId: string,
  signal?: AbortSignal,
): Promise<StrategyEvaluationDetailResponse> {
  return apiGet<StrategyEvaluationDetailResponse>(
    `/research/strategy-evaluations/${encodeURIComponent(evaluationId)}`,
    signal,
  );
}

export function fetchResearchCapabilities(signal?: AbortSignal): Promise<ResearchCapabilitiesResponse> {
  return apiGet<ResearchCapabilitiesResponse>("/research/capabilities", signal);
}

export function fetchProjectStudies(
  projectId: number,
  signal?: AbortSignal,
  track?: string,
): Promise<ProjectStudiesResponse> {
  const query = new URLSearchParams({ limit: "500", sort_by: "registered_at", sort_order: "desc" });
  if (track) query.set("track", track);
  return apiGet<ProjectStudiesResponse>(`/projects/${projectId}/studies?${query}`, signal);
}

export function registerProjectStudy(
  projectId: number,
  payload: StudyRegistrationPayload,
  idempotencyKey: string,
): Promise<StudySubmissionResponse> {
  return apiPost<StudySubmissionResponse>(
    `/projects/${projectId}/studies`,
    payload,
    { "Idempotency-Key": idempotencyKey },
  );
}

export function fetchProjectStudy(
  projectId: number,
  studyId: string,
  signal?: AbortSignal,
): Promise<StudyDetailResponse> {
  return apiGet<StudyDetailResponse>(
    `/projects/${projectId}/studies/${encodeURIComponent(studyId)}`,
    signal,
  );
}

export function fetchProjectStudyIntegrity(
  projectId: number,
  studyId: string,
  signal?: AbortSignal,
): Promise<StudyIntegrityResponse> {
  return apiGet<StudyIntegrityResponse>(
    `/projects/${projectId}/studies/${encodeURIComponent(studyId)}/integrity`,
    signal,
  );
}

export function fetchProjectStudyAnalyses(
  projectId: number,
  studyId: string,
  signal?: AbortSignal,
): Promise<StudyAnalysesResponse> {
  return apiGet<StudyAnalysesResponse>(
    `/projects/${projectId}/studies/${encodeURIComponent(studyId)}/analyses?limit=100&offset=0`,
    signal,
  );
}

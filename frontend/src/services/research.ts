import { apiGet } from "./api";

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

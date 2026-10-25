import type { MetaInfo } from "../types/dashboard";
import type {
  CreateInvestigationRequest,
  InvestigationDetail,
  InvestigationListResponse,
  Scenario,
  TimelineResponse,
} from "../types/investigations";
import { apiGet, apiPost } from "./api";

export type LoopStrategy = "fixed_order" | "risk_score" | "information_value" | "experience" | "llm";
export type LoopDataPartition = "training" | "validation" | "test" | "held_out_family";

export interface CreateInvestigationLoopRequest {
  submission_id: string;
  strategy: LoopStrategy;
  max_actions: number;
  max_seconds: number;
  max_model_calls: number;
  no_new_evidence_rounds: number;
  data_partition: LoopDataPartition;
  authorization_ref?: string | null;
}

export interface InvestigationLoopSubmissionResponse {
  meta: { data_mode: "live"; source: "agentguard" };
  submission: {
    submission_id: string;
    status: "PREPARED" | "SUBMITTING" | "SUBMISSION_AMBIGUOUS" | "LINK_PENDING" | "COMPLETED" | "FAILED";
    loop_id: string | null;
    created_at: string | null;
    error: { code: string; message: string } | null;
  };
  loop: Record<string, unknown> | null;
}

export function fetchInvestigations(
  params: { status?: string; limit?: number; offset?: number },
  signal?: AbortSignal,
): Promise<InvestigationListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  query.set("limit", String(params.limit ?? 50));
  query.set("offset", String(params.offset ?? 0));
  return apiGet<InvestigationListResponse>(`/investigations?${query.toString()}`, signal);
}

export function fetchInvestigation(
  requestId: string,
  signal?: AbortSignal,
): Promise<{ meta: MetaInfo; investigation: InvestigationDetail }> {
  return apiGet<{ meta: MetaInfo; investigation: InvestigationDetail }>(
    `/investigations/${encodeURIComponent(requestId)}`,
    signal,
  );
}

export function fetchTimeline(
  requestId: string,
  signal?: AbortSignal,
): Promise<TimelineResponse> {
  return apiGet<TimelineResponse>(`/investigations/${encodeURIComponent(requestId)}/timeline`, signal);
}

export function submitInvestigation(body: CreateInvestigationRequest): Promise<{
  meta: MetaInfo;
  created: InvestigationDetail;
}> {
  return apiPost("/investigations", body);
}

export function submitInvestigationLoop(
  requestId: string,
  body: CreateInvestigationLoopRequest,
): Promise<InvestigationLoopSubmissionResponse> {
  return apiPost<InvestigationLoopSubmissionResponse>(
    `/investigations/${encodeURIComponent(requestId)}/loops`,
    body,
  );
}

export function fetchInvestigationLoopSubmission(
  requestId: string,
  submissionId: string,
  signal?: AbortSignal,
): Promise<InvestigationLoopSubmissionResponse> {
  return apiGet<InvestigationLoopSubmissionResponse>(
    `/investigations/${encodeURIComponent(requestId)}/loop-submissions/${encodeURIComponent(submissionId)}`,
    signal,
  );
}

export function reconcileInvestigationLoopSubmission(
  requestId: string,
  submissionId: string,
): Promise<InvestigationLoopSubmissionResponse> {
  return apiPost<InvestigationLoopSubmissionResponse>(
    `/investigations/${encodeURIComponent(requestId)}/loop-submissions/${encodeURIComponent(submissionId)}/reconcile`,
  );
}

export function fetchScenarios(signal?: AbortSignal): Promise<{ items: Scenario[] }> {
  return apiGet<{ items: Scenario[] }>("/scenarios", signal);
}

import type { MetaInfo } from "../types/dashboard";
import type {
  CreateInvestigationRequest,
  InvestigationDetail,
  InvestigationListResponse,
  Scenario,
  TimelineResponse,
} from "../types/investigations";
import { apiGet, apiPost } from "./api";

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

export function fetchScenarios(signal?: AbortSignal): Promise<{ items: Scenario[] }> {
  return apiGet<{ items: Scenario[] }>("/scenarios", signal);
}

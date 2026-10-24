import type { DefenseOutcomesResponse, DefenseResponse, EvidenceResponse } from "../types/evidence";
import { apiGet, apiPost } from "./api";

export function fetchEvidence(requestId: string, signal?: AbortSignal): Promise<EvidenceResponse> {
  return apiGet<EvidenceResponse>(`/evidence?request_id=${encodeURIComponent(requestId)}`, signal);
}

export function fetchDefense(requestId: string, signal?: AbortSignal): Promise<DefenseResponse> {
  return apiGet<DefenseResponse>(`/defense?request_id=${encodeURIComponent(requestId)}`, signal);
}

export function fetchDefenseOutcomes(signal?: AbortSignal): Promise<DefenseOutcomesResponse> {
  return apiGet<DefenseOutcomesResponse>("/defense/outcomes", signal);
}

export function postDefensePreview(requestId: string): Promise<DefenseResponse> {
  return apiPost<DefenseResponse>(`/defense/${encodeURIComponent(requestId)}/preview`);
}

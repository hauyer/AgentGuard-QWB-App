import type { GraphResponse } from "../types/graph";
import { apiGet } from "./api";

export function fetchGraph(requestId: string | null, signal?: AbortSignal): Promise<GraphResponse> {
  const query = requestId ? `?request_id=${encodeURIComponent(requestId)}` : "";
  return apiGet<GraphResponse>(`/interaction-graph${query}`, signal);
}

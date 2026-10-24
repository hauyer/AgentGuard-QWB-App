import type { DashboardResponse } from "../types/dashboard";
import { apiGet } from "./api";

export function fetchDashboard(signal?: AbortSignal): Promise<DashboardResponse> {
  return apiGet<DashboardResponse>("/dashboard", signal);
}

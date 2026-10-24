import type { SystemStatus } from "../types/system";
import { apiGet } from "./api";

export function fetchSystemStatus(signal?: AbortSignal): Promise<SystemStatus> {
  return apiGet<SystemStatus>("/system/status", signal);
}

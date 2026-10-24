/** Shared frontend types for BFF responses. */

export type DataMode = "live" | "recorded" | "synthetic" | "unavailable";

export interface ErrorInfo {
  code: string;
  message: string;
  request_id?: string | null;
}

export interface AgentGuardHealth {
  status: string;
  service?: string | null;
  version?: string | null;
}

export interface AgentGuardCapabilities {
  provider_id?: string | null;
  provider_version?: string | null;
  backend_mode?: string | null;
  capabilities: Record<string, boolean>;
  supported_target_types: string[];
  supported_operations: string[];
  limitations: string[];
}

export interface AgentGuardStatus {
  reachable: boolean;
  health?: AgentGuardHealth | null;
  capabilities?: AgentGuardCapabilities | null;
  error?: ErrorInfo | null;
}

export interface WardenStatusSummary {
  status: string;
  kernel?: string | null;
  base_url?: string | null;
  error_code?: string | null;
  reason?: string | null;
  authoritative_for?: string[];
}

export interface FeatureAvailability {
  name: string;
  available: boolean;
  reason?: string | null;
}

export interface SystemStatus {
  app: { name: string; version: string; status: string };
  data_mode: DataMode;
  agentguard: AgentGuardStatus;
  warden: WardenStatusSummary;
  capabilities?: AgentGuardCapabilities | null;
  features: FeatureAvailability[];
  unavailable_features: FeatureAvailability[];
  generated_at: string;
}

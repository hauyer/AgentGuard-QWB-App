import type { SystemStatus } from "./system";

export type DataMode = SystemStatus["data_mode"];

export interface MetaInfo {
  data_mode: DataMode;
  fixture_id?: string | null;
  source?: string | null;
  agentguard_version?: string | null;
  agentguard_commit?: string | null;
  collected_at?: string | null;
  sanitized?: boolean | null;
  not_provable?: string[];
}

export interface InvestigationSummary {
  available: boolean;
  sample_based: boolean;
  total?: number | null;
  running?: number | null;
  completed?: number | null;
  blocked?: number | null;
  failed?: number | null;
  pending?: number | null;
  recent_request_id?: string | null;
  recent_status?: string | null;
  error?: string | null;
}

export interface EvidenceSummary {
  available: boolean;
  sample_based: boolean;
  by_level: Record<string, number>;
  by_verification: Record<string, number>;
  recent_count?: number | null;
  error?: string | null;
}

export interface PolicySummary {
  available: boolean;
  sample_based: boolean;
  pending_approval?: number | null;
  approved?: number | null;
  unsupported?: number | null;
  verified_historical?: number | null;
  error?: string | null;
}

export interface DependencyBlocker {
  id: string;
  title: string;
  impact: string;
  status: string;
}

export interface AuditCapability {
  name: string;
  enabled: boolean;
  note?: string | null;
}

export interface DashboardResponse {
  system: SystemStatus;
  investigation_summary: InvestigationSummary;
  evidence_summary: EvidenceSummary;
  policy_summary: PolicySummary;
  dependency_blockers: DependencyBlocker[];
  audit_capabilities: AuditCapability[];
  meta: MetaInfo;
}

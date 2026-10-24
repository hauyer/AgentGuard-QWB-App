/** Project management types (B18 UI for the B12 backend contract). */

export type ProjectStatus = "active" | "archived";
export type ProjectRole = "viewer" | "analyst" | "operator" | "admin";

export interface ProjectMember {
  username: string;
  role: ProjectRole;
  added_by?: string | null;
  added_at?: string | null;
}

export interface Project {
  project_id: number;
  name: string;
  description?: string | null;
  status: ProjectStatus;
  created_by?: string | null;
  created_at?: string | null;
  investigation_count: number;
  members?: ProjectMember[];
}

export interface ProjectsResponse {
  count: number;
  total: number;
  offset: number;
  limit: number;
  items: Project[];
}

export interface ProjectDetailResponse {
  project: Project;
  membership_role: string;
}

export interface ProjectInvestigationRef {
  agentguard_request_id: string;
  display_name?: string | null;
  notes?: string | null;
  verification: string;
  created_by?: string | null;
  created_at?: string | null;
}

export interface ProjectInvestigationsResponse {
  count: number;
  items: ProjectInvestigationRef[];
}

export interface MembersResponse {
  count: number;
  items: ProjectMember[];
}

export interface AuditEvent {
  id?: number;
  actor: string;
  role?: string | null;
  action: string;
  target?: string | null;
  project_id?: number | null;
  detail?: string | null;
  at?: string | null;
}

export interface AuditEventsResponse {
  count: number;
  total: number;
  offset: number;
  limit: number;
  persisted: boolean;
  items: AuditEvent[];
}

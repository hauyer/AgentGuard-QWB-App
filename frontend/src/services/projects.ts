/** Project management BFF service (B12 contract). */

import { apiDelete, apiGet, apiPatch, apiPost } from "./api";
import type {
  MembersResponse,
  Project,
  ProjectDetailResponse,
  ProjectInvestigationRef,
  ProjectInvestigationsResponse,
  ProjectRole,
  ProjectStatus,
  ProjectsResponse,
} from "../types/projects";

export function fetchProjects(limit = 50, offset = 0, signal?: AbortSignal): Promise<ProjectsResponse> {
  return apiGet<ProjectsResponse>(`/projects?limit=${limit}&offset=${offset}`, signal);
}

export function fetchProject(projectId: number, signal?: AbortSignal): Promise<ProjectDetailResponse> {
  return apiGet<ProjectDetailResponse>(`/projects/${projectId}`, signal);
}

export function createProject(name: string, description: string | null): Promise<{ created: Project }> {
  return apiPost<{ created: Project }>("/projects", { name, description });
}

export function updateProject(
  projectId: number,
  patch: { description?: string | null; status?: ProjectStatus },
): Promise<{ updated: Project }> {
  return apiPatch<{ updated: Project }>(`/projects/${projectId}`, patch);
}

export function fetchMembers(projectId: number, signal?: AbortSignal): Promise<MembersResponse> {
  return apiGet<MembersResponse>(`/projects/${projectId}/members`, signal);
}

export function addMember(projectId: number, username: string, role: ProjectRole): Promise<{ added: unknown }> {
  return apiPost<{ added: unknown }>(`/projects/${projectId}/members`, { username, role });
}

export function removeMember(projectId: number, username: string): Promise<{ removed: string }> {
  return apiDelete<{ removed: string }>(`/projects/${projectId}/members/${encodeURIComponent(username)}`);
}

export function fetchProjectInvestigations(
  projectId: number,
  signal?: AbortSignal,
): Promise<ProjectInvestigationsResponse> {
  return apiGet<ProjectInvestigationsResponse>(`/projects/${projectId}/investigations`, signal);
}

export function linkInvestigation(
  projectId: number,
  agentguardRequestId: string,
  displayName: string | null,
  notes: string | null,
): Promise<{ linked: ProjectInvestigationRef }> {
  return apiPost<{ linked: ProjectInvestigationRef }>(`/projects/${projectId}/investigations`, {
    agentguard_request_id: agentguardRequestId,
    display_name: displayName,
    notes,
  });
}

export function unlinkInvestigation(projectId: number, requestId: string): Promise<{ unlinked: string }> {
  return apiDelete<{ unlinked: string }>(
    `/projects/${projectId}/investigations/${encodeURIComponent(requestId)}`,
  );
}

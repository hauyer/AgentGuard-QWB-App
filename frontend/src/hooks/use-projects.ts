import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addMember,
  createProject,
  fetchMembers,
  fetchProject,
  fetchProjectInvestigations,
  fetchProjects,
  linkInvestigation,
  removeMember,
  unlinkInvestigation,
  updateProject,
} from "../services/projects";
import type { ProjectRole, ProjectStatus } from "../types/projects";

export function useProjects(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["projects", limit, offset],
    queryFn: ({ signal }) => fetchProjects(limit, offset, signal),
    placeholderData: (previous) => previous,
  });
}

export function useProject(projectId: number) {
  return useQuery({
    queryKey: ["project", projectId],
    queryFn: ({ signal }) => fetchProject(projectId, signal),
    enabled: Number.isFinite(projectId) && projectId > 0,
  });
}

export function useProjectMembers(projectId: number) {
  return useQuery({
    queryKey: ["project-members", projectId],
    queryFn: ({ signal }) => fetchMembers(projectId, signal),
    enabled: Number.isFinite(projectId) && projectId > 0,
  });
}

export function useProjectInvestigations(projectId: number) {
  return useQuery({
    queryKey: ["project-investigations", projectId],
    queryFn: ({ signal }) => fetchProjectInvestigations(projectId, signal),
    enabled: Number.isFinite(projectId) && projectId > 0,
  });
}

export function useInvalidateProject() {
  const queryClient = useQueryClient();
  return (projectId?: number) => {
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
    if (projectId !== undefined) {
      void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["project-members", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["project-investigations", projectId] });
    }
    void queryClient.invalidateQueries({ queryKey: ["audit"] });
  };
}

export function useCreateProject() {
  const invalidate = useInvalidateProject();
  return useMutation({
    mutationFn: ({ name, description }: { name: string; description: string | null }) =>
      createProject(name, description),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateProject(projectId: number) {
  const invalidate = useInvalidateProject();
  return useMutation({
    mutationFn: (patch: { description?: string | null; status?: ProjectStatus }) =>
      updateProject(projectId, patch),
    onSuccess: () => invalidate(projectId),
  });
}

export function useAddMember(projectId: number) {
  const invalidate = useInvalidateProject();
  return useMutation({
    mutationFn: ({ username, role }: { username: string; role: ProjectRole }) =>
      addMember(projectId, username, role),
    onSuccess: () => invalidate(projectId),
  });
}

export function useRemoveMember(projectId: number) {
  const invalidate = useInvalidateProject();
  return useMutation({
    mutationFn: (username: string) => removeMember(projectId, username),
    onSuccess: () => invalidate(projectId),
  });
}

export function useLinkInvestigation(projectId: number) {
  const invalidate = useInvalidateProject();
  return useMutation({
    mutationFn: ({ requestId, displayName, notes }: { requestId: string; displayName: string | null; notes: string | null }) =>
      linkInvestigation(projectId, requestId, displayName, notes),
    onSuccess: () => invalidate(projectId),
  });
}

export function useLinkInvestigationToProject() {
  const invalidate = useInvalidateProject();
  return useMutation({
    mutationFn: ({ projectId, requestId }: { projectId: number; requestId: string }) =>
      linkInvestigation(projectId, requestId, null, null),
    onSuccess: (_data, variables) => invalidate(variables.projectId),
  });
}

export function useUnlinkInvestigation(projectId: number) {
  const invalidate = useInvalidateProject();
  return useMutation({
    mutationFn: (requestId: string) => unlinkInvestigation(projectId, requestId),
    onSuccess: () => invalidate(projectId),
  });
}

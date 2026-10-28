import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchProjectStudies,
  fetchProjectStudy,
  fetchProjectStudyAnalyses,
  fetchProjectStudyIntegrity,
  fetchResearchCapabilities,
  registerProjectStudy,
} from "../services/research";
import type { StudyRegistrationPayload } from "../services/research";

export function useResearchCapabilities() {
  return useQuery({
    queryKey: ["research", "capabilities"],
    queryFn: ({ signal }) => fetchResearchCapabilities(signal),
    staleTime: 15_000,
  });
}

export function useProjectStudies(projectId: number, track?: string) {
  return useQuery({
    queryKey: ["project-studies", projectId, track ?? null],
    queryFn: ({ signal }) => fetchProjectStudies(projectId, signal, track),
    enabled: Number.isFinite(projectId) && projectId > 0,
  });
}

export function useProjectStudy(projectId: number, studyId: string | null) {
  return useQuery({
    queryKey: ["project-study", projectId, studyId],
    queryFn: ({ signal }) => fetchProjectStudy(projectId, studyId!, signal),
    enabled: projectId > 0 && Boolean(studyId),
  });
}

export function useProjectStudyIntegrity(projectId: number, studyId: string | null) {
  return useQuery({
    queryKey: ["project-study-integrity", projectId, studyId],
    queryFn: ({ signal }) => fetchProjectStudyIntegrity(projectId, studyId!, signal),
    enabled: projectId > 0 && Boolean(studyId),
  });
}

export function useProjectStudyAnalyses(projectId: number, studyId: string | null) {
  return useQuery({
    queryKey: ["project-study-analyses", projectId, studyId],
    queryFn: ({ signal }) => fetchProjectStudyAnalyses(projectId, studyId!, signal),
    enabled: projectId > 0 && Boolean(studyId),
  });
}

export function useRegisterProjectStudy(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ payload, idempotencyKey }: {
      payload: StudyRegistrationPayload;
      idempotencyKey: string;
    }) => registerProjectStudy(projectId, payload, idempotencyKey),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["project-studies", projectId] });
    },
  });
}

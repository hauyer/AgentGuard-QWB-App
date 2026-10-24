import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchInvestigation,
  fetchInvestigations,
  fetchScenarios,
  fetchTimeline,
  submitInvestigation,
} from "../services/investigations";
import type { CreateInvestigationRequest } from "../types/investigations";

export function useInvestigations(status: string | null, limit: number, offset: number) {
  return useQuery({
    queryKey: ["investigations", status, limit, offset],
    queryFn: ({ signal }) => fetchInvestigations({ status: status ?? undefined, limit, offset }, signal),
    placeholderData: (previous) => previous,
  });
}

export function useInvestigation(requestId: string) {
  return useQuery({
    queryKey: ["investigation", requestId],
    queryFn: ({ signal }) => fetchInvestigation(requestId, signal),
    enabled: requestId.length > 0,
  });
}

export function useTimeline(requestId: string) {
  return useQuery({
    queryKey: ["timeline", requestId],
    queryFn: ({ signal }) => fetchTimeline(requestId, signal),
    enabled: requestId.length > 0,
  });
}

export function useCreateInvestigation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateInvestigationRequest) => submitInvestigation(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["investigations"] });
    },
  });
}

export function useScenarios() {
  return useQuery({
    queryKey: ["scenarios"],
    queryFn: ({ signal }) => fetchScenarios(signal),
  });
}

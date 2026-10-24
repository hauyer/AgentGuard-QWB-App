import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchDefense, fetchDefenseOutcomes, fetchEvidence, postDefensePreview } from "../services/evidence";

export function useEvidence(requestId: string) {
  return useQuery({
    queryKey: ["evidence", requestId],
    queryFn: ({ signal }) => fetchEvidence(requestId, signal),
    enabled: Boolean(requestId),
  });
}

export function useDefense(requestId: string) {
  return useQuery({
    queryKey: ["defense", requestId],
    queryFn: ({ signal }) => fetchDefense(requestId, signal),
    enabled: Boolean(requestId),
  });
}

export function useDefenseOutcomes() {
  return useQuery({
    queryKey: ["defense-outcomes"],
    queryFn: ({ signal }) => fetchDefenseOutcomes(signal),
  });
}

export function usePreviewDefense(requestId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => postDefensePreview(requestId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["defense", requestId] });
    },
  });
}

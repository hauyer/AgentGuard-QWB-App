import { useMutation, useQuery } from "@tanstack/react-query";

import {
  fetchInvestigationLoopSubmission,
  reconcileInvestigationLoopSubmission,
  submitInvestigationLoop,
} from "../services/investigations";
import type {
  CreateInvestigationLoopRequest,
} from "../services/investigations";

export function useCreateInvestigationLoop(requestId: string) {
  return useMutation({
    mutationFn: (body: CreateInvestigationLoopRequest) => submitInvestigationLoop(requestId, body),
  });
}

export function useInvestigationLoopSubmission(requestId: string, submissionId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["investigation-loop-submission", requestId, submissionId],
    queryFn: ({ signal }) => fetchInvestigationLoopSubmission(requestId, submissionId, signal),
    enabled,
    retry: false,
    staleTime: 0,
  });
}

export function useReconcileInvestigationLoop(requestId: string) {
  return useMutation({
    mutationFn: (submissionId: string) => reconcileInvestigationLoopSubmission(requestId, submissionId),
  });
}

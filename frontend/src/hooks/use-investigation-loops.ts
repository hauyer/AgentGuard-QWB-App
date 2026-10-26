import { useMutation, useQuery } from "@tanstack/react-query";

import {
  fetchInvestigationLoops,
  fetchInvestigationLoopSubmission,
  reconcileInvestigationLoopSubmission,
  submitInvestigationLoop,
} from "../services/investigations";
import type {
  CreateInvestigationLoopRequest,
  ReconcileLoopSubmissionRequest,
} from "../services/investigations";

export function useCreateInvestigationLoop(requestId: string) {
  return useMutation({
    mutationFn: (body: CreateInvestigationLoopRequest) => submitInvestigationLoop(requestId, body),
  });
}

export function useInvestigationLoops(requestId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["investigation-loops", requestId],
    queryFn: ({ signal }) => fetchInvestigationLoops(requestId, signal),
    enabled: enabled && requestId.length > 0,
    staleTime: 15_000,
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
    mutationFn: (input: { submissionId: string; body: ReconcileLoopSubmissionRequest }) =>
      reconcileInvestigationLoopSubmission(requestId, input.submissionId, input.body),
  });
}

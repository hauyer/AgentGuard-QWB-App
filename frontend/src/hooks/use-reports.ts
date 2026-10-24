import { useQuery } from "@tanstack/react-query";

import { fetchExperiences, fetchExperiments, fetchReport } from "../services/reports";

export function useExperiments() {
  return useQuery({
    queryKey: ["experiments"],
    queryFn: ({ signal }) => fetchExperiments(signal),
  });
}

export function useReport(runId: string) {
  return useQuery({
    queryKey: ["report", runId],
    queryFn: ({ signal }) => fetchReport(runId, signal),
    enabled: Boolean(runId),
  });
}

export function useExperiences() {
  return useQuery({
    queryKey: ["experiences"],
    queryFn: ({ signal }) => fetchExperiences(signal),
  });
}

import { useQuery } from "@tanstack/react-query";

import { fetchDashboard } from "../services/dashboard";

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: ({ signal }) => fetchDashboard(signal),
    refetchInterval: 30_000,
  });
}

import { useQuery } from "@tanstack/react-query";

import { fetchSystemStatus } from "../services/system";
import type { SystemStatus } from "../types/system";

export function useSystemStatus() {
  return useQuery<SystemStatus>({
    queryKey: ["system", "status"],
    queryFn: ({ signal }) => fetchSystemStatus(signal),
  });
}

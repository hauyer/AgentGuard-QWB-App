import { useQuery } from "@tanstack/react-query";

import { fetchGraph } from "../services/graph";

export function useGraph(requestId: string | null) {
  return useQuery({
    queryKey: ["graph", requestId],
    queryFn: ({ signal }) => fetchGraph(requestId, signal),
  });
}

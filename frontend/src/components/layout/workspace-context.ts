import { useOutletContext } from "react-router-dom";
export interface WorkspaceChrome { setSource: (source: string | null) => void }
export function useWorkspaceChrome(): WorkspaceChrome | undefined {
  return useOutletContext<WorkspaceChrome | undefined>();
}

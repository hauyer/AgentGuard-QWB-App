import { useSearchParams } from "react-router-dom";
/** Resource selection follows the URL, including refresh and browser back/forward. */
export function useResourceSelection(key: "request_id" | "run_id") {
  const [params, setParams] = useSearchParams();
  const value = params.get(key) ?? "";
  const select = (id: string) => {
    const next = new URLSearchParams(params);
    if (id.trim()) next.set(key, id.trim()); else next.delete(key);
    setParams(next);
  };
  return [value, select] as const;
}

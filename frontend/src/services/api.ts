/** Typed fetch wrapper for the BFF. The browser only ever calls the BFF /api. */

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly requestId?: string | null;

  constructor(status: number, message: string, code?: string, requestId?: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
    signal,
  });
  return parseResponse<T>(response);
}

async function parseResponse<T>(response: Response): Promise<T> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // non-JSON body; handled by the generic error below
  }
  if (!response.ok) {
    const detail = (payload as { detail?: { error?: string; message?: string; request_id?: string } })?.detail;
    throw new ApiError(
      response.status,
      detail?.message ?? detail?.error ?? `请求失败 (HTTP ${response.status})`,
      detail?.error,
      detail?.request_id,
    );
  }
  return payload as T;
}

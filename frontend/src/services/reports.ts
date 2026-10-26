import type {
  ExperimentsResponse,
  ExperiencesResponse,
  InvestigationLoopReportResponse,
  ReportResponse,
} from "../types/reports";
import { apiGet, apiPost } from "./api";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export function fetchExperiments(signal?: AbortSignal): Promise<ExperimentsResponse> {
  return apiGet<ExperimentsResponse>("/experiments", signal);
}

/** B13 controlled comparison: the backend verifies comparability first. */
export function postExperimentsCompare(runIds: string[]): Promise<unknown> {
  return apiPost<unknown>("/experiments/compare", { run_ids: runIds });
}

export function fetchReport(runId: string, signal?: AbortSignal): Promise<ReportResponse> {
  return apiGet<ReportResponse>(`/reports/${encodeURIComponent(runId)}`, signal);
}

export function fetchInvestigationLoopReport(
  requestId: string,
  loopId: string,
  signal?: AbortSignal,
): Promise<InvestigationLoopReportResponse> {
  return apiGet<InvestigationLoopReportResponse>(
    `/reports/investigations/${encodeURIComponent(requestId)}/loops/${encodeURIComponent(loopId)}`,
    signal,
  );
}

export function fetchExperiences(signal?: AbortSignal): Promise<ExperiencesResponse> {
  return apiGet<ExperiencesResponse>("/experiences", signal);
}

/** JSON download: re-fetch the report through the BFF and save as a file. */
export async function downloadReportJson(runId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/reports/${encodeURIComponent(runId)}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`报告下载失败 (HTTP ${response.status})`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `report-${runId}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

/** PDF export: the BFF generates the PDF from report fields as-is. */
export function downloadReportPdf(runId: string): void {
  const link = document.createElement("a");
  link.href = `${API_BASE}/reports/${encodeURIComponent(runId)}/export`;
  link.download = `report-${runId}.pdf`;
  link.click();
}

export function downloadInvestigationLoopReportJson(requestId: string, loopId: string): Promise<void> {
  return downloadBffFile(
    `/reports/investigations/${encodeURIComponent(requestId)}/loops/${encodeURIComponent(loopId)}/export.json`,
    `investigation-report-${requestId}-${loopId}.json`,
  );
}

export function downloadInvestigationLoopReportPdf(requestId: string, loopId: string): Promise<void> {
  return downloadBffFile(
    `/reports/investigations/${encodeURIComponent(requestId)}/loops/${encodeURIComponent(loopId)}/export.pdf`,
    `investigation-report-${requestId}-${loopId}.pdf`,
  );
}

async function downloadBffFile(path: string, fallbackName: string): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, { headers: { Accept: "*/*" } });
  if (!response.ok) {
    let message = `报告下载失败 (HTTP ${response.status})`;
    try {
      const payload = await response.json() as { detail?: { message?: string; error?: string } };
      message = payload.detail?.message ?? payload.detail?.error ?? message;
    } catch {
      // Keep the bounded status message for non-JSON error responses.
    }
    throw new Error(message);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="([A-Za-z0-9._-]+)"/i)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

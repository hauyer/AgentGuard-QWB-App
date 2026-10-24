import type { ExperimentsResponse, ExperiencesResponse, ReportResponse } from "../types/reports";
import { apiGet } from "./api";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export function fetchExperiments(signal?: AbortSignal): Promise<ExperimentsResponse> {
  return apiGet<ExperimentsResponse>("/experiments", signal);
}

export function fetchReport(runId: string, signal?: AbortSignal): Promise<ReportResponse> {
  return apiGet<ReportResponse>(`/reports/${encodeURIComponent(runId)}`, signal);
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

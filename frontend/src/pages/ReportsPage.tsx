import { useState } from "react";

import { useAuthStore } from "../stores/auth-store";
import { useReport } from "../hooks/use-reports";
import { downloadReportJson, downloadReportPdf } from "../services/reports";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import { EvidenceLevelBadge } from "../components/shared/evidence-level-badge";
import { VerificationBadge } from "../components/shared/verification-badge";

const SAMPLE_RUNS = ["run-qwb-0001"];

export function ReportsPage() {
  const role = useAuthStore((state) => state.role);
  const [runId, setRunId] = useState(SAMPLE_RUNS[0]);
  const { data, isLoading, error, refetch, isFetching } = useReport(runId);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const report = data?.report;
  const meta = data?.meta;

  const onJson = async () => {
    setDownloadError(null);
    try {
      await downloadReportJson(runId);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : "JSON 下载失败");
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="报告中心"
        description="调查报告预览、证据摘要与防御候选汇总。PDF 由应用层生成，不改指标、不推断新的因果结论。"
      />

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-slate-500">运行：</span>
        <select
          value={runId}
          onChange={(event) => setRunId(event.target.value)}
          className="rounded-md border border-surface-border px-2 py-1 text-xs"
        >
          {SAMPLE_RUNS.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
        <Button variant="secondary" onClick={() => void onJson()} disabled={!report}>
          下载 JSON
        </Button>
        <Button variant="secondary" onClick={() => downloadReportPdf(runId)} disabled={!report}>
          导出 PDF
        </Button>
      </div>

      {downloadError && <p className="text-xs text-red-600">{downloadError}</p>}

      {isLoading && <p className="text-sm text-slate-400">正在加载报告…</p>}

      {error && (
        <ErrorState
          title="报告不可用"
          message={error instanceof Error ? error.message : "无法获取报告"}
          code={(error as { code?: string }).code}
          requestId={(error as { requestId?: string | null }).requestId}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {data && meta && <DemoBanner meta={meta} />}

      {report && (
        <>
          <Card title={`调查运行 ${report.run_id ?? runId}`}>
            <div className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
              <div>
                <dt className="text-slate-400">request_id</dt>
                <dd className="font-mono text-slate-700">{report.request_id ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-400">experiment_id</dt>
                <dd className="font-mono text-slate-700">{report.experiment_id ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-400">scenario_id</dt>
                <dd className="font-mono text-slate-700">{report.scenario_id ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-400">状态 / 策略画像</dt>
                <dd className="text-slate-700">
                  {report.status ?? "—"} · {report.policy_profile ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">创建时间</dt>
                <dd className="font-mono text-slate-700">{report.created_at ?? "—"}</dd>
              </div>
            </div>
          </Card>

          <Card title="风险发现">
            {report.findings.length === 0 ? (
              <p className="text-sm text-slate-400">（无）</p>
            ) : (
              <div className="space-y-2">
                {report.findings.map((finding) => (
                  <div key={finding.finding_id} className="rounded-md border border-surface-border p-3 text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-slate-700">{finding.finding_id}</span>
                      <Badge variant={finding.severity === "high" ? "danger" : finding.severity === "medium" ? "warn" : "neutral"}>
                        {finding.severity ?? "—"}
                      </Badge>
                      <Badge variant="neutral">{finding.risk_type ?? "—"}</Badge>
                    </div>
                    <p className="mt-1 text-slate-600">{finding.summary}</p>
                    <p className="mt-1 font-mono text-[10px] text-slate-400">
                      evidence: {finding.evidence_ids.join(", ") || "—"}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="证据摘要">
            {report.evidence.length === 0 ? (
              <p className="text-sm text-slate-400">（无）</p>
            ) : (
              <div className="space-y-1">
                {report.evidence.map((item) => (
                  <div key={item.evidence_id} className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="font-mono text-slate-700">{item.evidence_id}</span>
                    {item.evidence_level && <EvidenceLevelBadge level={item.evidence_level} />}
                    {item.verification_status && <VerificationBadge status={item.verification_status} />}
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="防御候选汇总">
            {report.defense_candidates.length === 0 ? (
              <p className="text-sm text-slate-400">（无）</p>
            ) : (
              <div className="space-y-1 text-xs">
                {report.defense_candidates.map((candidate) => (
                  <div key={candidate.candidate_id} className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-slate-700">{candidate.candidate_id}</span>
                    <Badge variant="neutral">{candidate.status ?? "—"}</Badge>
                    <Badge variant="neutral">
                      execution_supported={String(candidate.execution_supported ?? false)}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="已知限制">
            {report.limitations.map((limitation) => (
              <p key={limitation} className="text-xs text-amber-700">
                ⚠ {limitation}
              </p>
            ))}
          </Card>

          {report.source_note && (
            <Card title="结果来源">
              <p className="font-mono text-xs text-slate-600">{report.source_note}</p>
            </Card>
          )}
        </>
      )}

      <p className="text-[11px] text-slate-400">
        当前角色：<span className="font-mono">{role ?? "未登录"}</span>。PDF 导出由应用层生成，仅排版报告字段，
        不改变底层指标，不推断新的因果结论。
      </p>
    </div>
  );
}

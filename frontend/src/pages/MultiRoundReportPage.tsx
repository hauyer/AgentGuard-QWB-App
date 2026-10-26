import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { fetchInvestigationLoops, fetchInvestigations } from "../services/investigations";
import {
  downloadInvestigationLoopReportJson,
  downloadInvestigationLoopReportPdf,
  fetchInvestigationLoopReport,
} from "../services/reports";
import type { InvestigationLoopReport } from "../types/reports";

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "未提供";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return "未提供";
}

function JsonBlock({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <p className="text-sm text-slate-500">未提供</p>;
  if (Array.isArray(value) && value.length === 0) return <p className="text-sm text-slate-500">无记录</p>;
  return (
    <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-[11px] leading-5 text-slate-700">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function evidenceReferences(data: Record<string, unknown> | null, side: "supporting" | "contradicting") {
  if (!data) return null;
  const keys = side === "supporting"
    ? ["supporting_evidence_refs", "supporting_evidence"]
    : ["contradicting_evidence_refs", "contradicting_evidence"];
  const groups: Array<{ record_id: string; evidence_refs: unknown }> = [];
  let fieldProvided = false;
  for (const [collection, idKey] of [["findings", "finding_id"], ["hypotheses", "hypothesis_id"]] as const) {
    const records = data[collection];
    if (!Array.isArray(records)) continue;
    for (const record of records) {
      if (typeof record !== "object" || record === null) continue;
      const row = record as Record<string, unknown>;
      const field = keys.find((key) => Object.prototype.hasOwnProperty.call(row, key));
      if (!field) continue;
      fieldProvided = true;
      groups.push({ record_id: display(row[idKey]), evidence_refs: row[field] });
    }
  }
  return fieldProvided ? groups : null;
}

function InfoField({ label, value }: { label: string; value: unknown }) {
  return <div><dt className="text-slate-500">{label}</dt><dd className="break-all font-mono">{display(value)}</dd></div>;
}

function ReportView({ report }: { report: InvestigationLoopReport }) {
  const investigation = report.investigation;
  const loop = report.loop;
  const defense = report.defense.data;
  const executionStatus = defense?.execution_performed === true
    ? "已执行"
    : defense?.execution_performed === false
      ? "未执行"
      : "未提供";

  return (
    <div className="space-y-4" data-testid="live-investigation-report">
      <Card title="项目与调查基本信息">
        <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <InfoField label="项目" value={report.project.name} />
          <InfoField label="项目状态" value={report.project.status} />
          <InfoField label="项目 ID" value={report.project.project_id} />
          <InfoField label="基础调查 ID" value={investigation.request_id} />
          <InfoField label="调查状态" value={investigation.status ?? investigation.workflow_status} />
          <InfoField label="场景 ID" value={investigation.scenario_id} />
          <InfoField label="模型 ID" value={investigation.model_id} />
          <InfoField label="运行环境 ID" value={investigation.runtime_id} />
          <InfoField label="运行 ID" value={investigation.run_id} />
        </dl>
      </Card>

      <Card title="Loop 状态与停止原因">
        <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <InfoField label="Loop ID" value={loop.loop_id} />
          <InfoField label="阶段" value={loop.phase} />
          <InfoField label="策略" value={loop.strategy} />
          <InfoField label="停止原因" value={loop.stop_reason} />
          <InfoField label="降级状态" value={loop.degradation} />
        </dl>
      </Card>

      <Card title="风险发现、假设与证据">
        {report.risk_analysis.available ? <JsonBlock value={report.risk_analysis.data} /> : (
          <p className="text-sm text-slate-500">未提供风险分析（{display(report.risk_analysis.error_code)}）。</p>
        )}
        {report.risk_analysis.available && (
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            <div><h3 className="mb-2 text-xs font-medium text-slate-600">支持证据引用</h3>
              <JsonBlock value={evidenceReferences(report.risk_analysis.data, "supporting")} /></div>
            <div><h3 className="mb-2 text-xs font-medium text-slate-600">反对/矛盾证据引用</h3>
              <JsonBlock value={evidenceReferences(report.risk_analysis.data, "contradicting")} /></div>
          </div>
        )}
        <p className="mt-3 text-xs text-slate-500">风险分析与证据字段按上游原始记录展示；没有因果验证标记时不提升证据等级。</p>
      </Card>

      <Card title={`多轮决策（${report.decisions.items.length}）`}>
        {report.decisions.items.length === 0 ? <p className="text-sm text-slate-500">无决策记录。</p> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[780px] text-xs">
              <thead><tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-3">决定 ID</th><th className="py-2 pr-3">轮次</th><th className="py-2 pr-3">策略</th>
                <th className="py-2 pr-3">所选动作</th><th className="py-2 pr-3">结果</th>
                <th className="py-2 pr-3">新增证据</th><th className="py-2 pr-3">停止原因</th>
              </tr></thead>
              <tbody>{report.decisions.items.map((decision, index) => (
                <tr key={display(decision.decision_id) === "未提供" ? index : String(decision.decision_id)} className="border-b border-slate-100">
                  <td className="py-2 pr-3 font-mono">{display(decision.decision_id)}</td>
                  <td className="py-2 pr-3">{display(decision.round_index)}</td>
                  <td className="py-2 pr-3">{display(decision.strategy)}</td>
                  <td className="py-2 pr-3 font-mono">{display(decision.selected_action_id)}</td>
                  <td className="py-2 pr-3">{display(decision.result_status)}</td>
                  <td className="py-2 pr-3">{display(decision.new_evidence_count)}</td>
                  <td className="py-2 pr-3">{display(decision.stop_reason)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="证据变化">
        <JsonBlock value={report.evidence_changes.items} />
      </Card>

      <Card title="预算消耗">
        <JsonBlock value={report.budget} />
      </Card>

      <Card title="防御候选与实际验证状态">
        <p className="mb-2 text-sm">实际执行状态：<span className="font-medium">{executionStatus}</span></p>
        {report.defense.available ? <JsonBlock value={defense} /> : (
          <p className="text-sm text-slate-500">未提供防御候选（{display(report.defense.error_code)}）。</p>
        )}
        <p className="mt-3 text-xs text-slate-500">候选或预览状态不代表已经执行；只有上游 execution_performed=true 才标记为已执行。</p>
      </Card>

      <Card title="策略评价关联">
        <p className="text-sm text-slate-600">{report.strategy_evaluation_note}</p>
        {report.strategy_evaluation && <div className="mt-3"><JsonBlock value={report.strategy_evaluation} /></div>}
      </Card>

      <Card title="数据来源与研究限制">
        <JsonBlock value={report.data_sources} />
        <p className="mt-3 text-xs font-medium text-slate-600">限制</p>
        {report.limitations.length > 0 ? (
          <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-slate-500">
            {report.limitations.map((limitation, index) => <li key={`${index}-${limitation}`}>{limitation}</li>)}
          </ul>
        ) : <p className="mt-1 text-xs text-slate-500">未提供</p>}
      </Card>
    </div>
  );
}

export function MultiRoundReportPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [downloadError, setDownloadError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const requestIdParam = searchParams.get("request_id");
  const loopIdParam = searchParams.get("loop_id");
  const investigationsQuery = useQuery({
    queryKey: ["report-investigations"],
    queryFn: ({ signal }) => fetchInvestigations({ limit: 200, offset: 0 }, signal),
  });
  const liveMode = investigationsQuery.data?.meta.data_mode === "live";
  const investigations = useMemo(
    () => (liveMode ? investigationsQuery.data?.items ?? [] : []),
    [investigationsQuery.data?.items, liveMode],
  );
  const requestKnown = Boolean(requestIdParam && investigations.some((item) => item.request_id === requestIdParam));
  const loopsQuery = useQuery({
    queryKey: ["report-loops", requestIdParam],
    queryFn: ({ signal }) => fetchInvestigationLoops(requestIdParam ?? "", signal),
    enabled: requestKnown,
  });
  const loops = useMemo(
    () => (loopsQuery.data?.meta.ownership_verified === true ? loopsQuery.data.items : []),
    [loopsQuery.data?.items, loopsQuery.data?.meta.ownership_verified],
  );
  const selectedLoopId = loopIdParam ?? loops[0]?.loop_id ?? "";
  const loopKnown = Boolean(selectedLoopId && loops.some((item) => item.loop_id === selectedLoopId));

  useEffect(() => {
    if (requestKnown && !loopIdParam && loops[0]?.loop_id) {
      setSearchParams({ request_id: requestIdParam ?? "", loop_id: loops[0].loop_id }, { replace: true });
    }
  }, [loopIdParam, loops, requestIdParam, requestKnown, setSearchParams]);

  const reportQuery = useQuery({
    queryKey: ["investigation-loop-report", requestIdParam, selectedLoopId],
    queryFn: ({ signal }) => fetchInvestigationLoopReport(requestIdParam ?? "", selectedLoopId, signal),
    enabled: requestKnown && loopKnown,
  });

  const handleDownload = async (format: "json" | "pdf") => {
    if (!requestIdParam || !selectedLoopId) return;
    setDownloadError("");
    setDownloading(true);
    try {
      if (format === "json") await downloadInvestigationLoopReportJson(requestIdParam, selectedLoopId);
      else await downloadInvestigationLoopReportPdf(requestIdParam, selectedLoopId);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "报告下载失败");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="多轮调查报告"
        description="报告内容和导出文件均基于当前有权访问的 Live 项目调查与已验证 Loop 记录。"
      />

      {investigationsQuery.isLoading && <p className="text-sm text-slate-400">正在加载可访问的项目调查…</p>}
      {investigationsQuery.error && (
        <ErrorState title="调查列表不可用" message={investigationsQuery.error instanceof Error ? investigationsQuery.error.message : "无法获取项目调查"}
          onRetry={() => void investigationsQuery.refetch()} retrying={investigationsQuery.isFetching} />
      )}

      {investigationsQuery.data && !liveMode && (
        <Card title="Live 报告不可用">
          <p className="text-sm text-slate-600">当前为 {investigationsQuery.data.meta.data_mode} 数据模式。Recorded/Synthetic 数据不与 Live 项目报告混合。</p>
        </Card>
      )}

      {liveMode && (
        <Card title="选择报告来源">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-xs text-slate-500">
              项目调查
              <select
                className="mt-1 block w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800"
                data-testid="report-investigation-select"
                value={requestIdParam ?? ""}
                onChange={(event) => {
                  const next = event.target.value;
                  setDownloadError("");
                  setSearchParams(next ? { request_id: next } : {});
                }}
              >
                <option value="">选择项目调查</option>
                {investigations.map((item) => (
                  <option key={item.request_id} value={item.request_id}>
                    {item.request_id} · {item.scenario_id ?? "未提供场景"} · {item.status}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-500">
              已验证 Loop
              <select
                className="mt-1 block w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800"
                data-testid="report-loop-select"
                value={loopKnown ? selectedLoopId : ""}
                disabled={!requestKnown || loops.length === 0}
                onChange={(event) => setSearchParams(event.target.value
                  ? { request_id: requestIdParam ?? "", loop_id: event.target.value }
                  : { request_id: requestIdParam ?? ""})}
              >
                <option value="">选择已验证 Loop</option>
                {loops.map((item) => <option key={item.loop_id} value={item.loop_id}>{item.loop_id} · {item.phase ?? "未提供状态"}</option>)}
              </select>
            </label>
          </div>
          {investigations.length === 0 && <p className="mt-3 text-sm text-slate-500">当前没有可访问的 Live 项目调查。</p>}
          {loopsQuery.isLoading && <p className="mt-3 text-sm text-slate-400">正在加载已验证 Loop…</p>}
          {loopsQuery.error && <p role="alert" className="mt-3 text-sm text-red-700">{loopsQuery.error instanceof Error ? loopsQuery.error.message : "无法获取 Loop 列表"}</p>}
          {requestKnown && !loopsQuery.isLoading && !loopsQuery.error && loops.length === 0 && (
            <p className="mt-3 text-sm text-slate-500">该调查尚无可验证的 Loop 报告来源。</p>
          )}
          <p className="mt-3 text-xs text-slate-500">报告预览与下载均会再次检查项目授权和 Loop 归属。</p>
        </Card>
      )}

      {reportQuery.isLoading && <p className="text-sm text-slate-400">正在汇总已验证的调查报告…</p>}
      {reportQuery.error && (
        <ErrorState title="调查报告不可用" message={reportQuery.error instanceof Error ? reportQuery.error.message : "无法获取报告"}
          onRetry={() => void reportQuery.refetch()} retrying={reportQuery.isFetching} />
      )}

      {reportQuery.data && requestIdParam && selectedLoopId && (
        <>
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={downloading} onClick={() => void handleDownload("json")}
              className="rounded-md bg-slate-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50">
              下载 JSON
            </button>
            <button type="button" disabled={downloading} onClick={() => void handleDownload("pdf")}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">
              导出 PDF
            </button>
            <Link to={`/investigations/${encodeURIComponent(requestIdParam)}/workspace`}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
              返回调查工作区
            </Link>
          </div>
          {downloadError && <p role="alert" className="text-sm text-red-700">{downloadError}</p>}
          <p className="text-xs text-slate-500">来源模式：{reportQuery.data.report.data_mode} · 生成时间：{reportQuery.data.report.generated_at}</p>
          <ReportView report={reportQuery.data.report} />
        </>
      )}
    </div>
  );
}

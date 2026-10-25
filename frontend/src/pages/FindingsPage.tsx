import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import { cn } from "../utils/cn";

import type { MetaInfo } from "../types/dashboard";

const SAMPLE_RUN_IDS = ["run-qwb-0001"];

interface Finding {
  finding_id: string;
  category: string;
  detection_method: string;
  severity: "low" | "medium" | "high" | "critical";
  score: number;
  calibrated: boolean;
  evidence_ids: string[];
  graph_nodes: string[];
  unverified: string;
  verification_status: string;
}

interface FindingsResponse {
  meta: MetaInfo;
  items: Finding[];
}

async function fetchFindings(runId: string, signal?: AbortSignal): Promise<FindingsResponse> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/findings`, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

const severityColor = {
  low: "bg-blue-50 text-blue-700",
  medium: "bg-yellow-50 text-yellow-700",
  high: "bg-orange-50 text-orange-700",
  critical: "bg-red-50 text-red-700",
};

export function FindingsPage() {
  const [searchParams] = useSearchParams();
  const initialRunId = searchParams.get("run_id") ?? SAMPLE_RUN_IDS[0];
  const [runId, setRunId] = useState(initialRunId);
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["findings", runId],
    queryFn: ({ signal }) => fetchFindings(runId, signal),
  });

  const findings = data?.items ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <PageHeader
        title="风险发现"
        description="AgentGuard E1 风险分析结果。每项风险显示类别、检测方法、严重程度、评分校准状态、支持证据与尚未证实的内容。"
      />

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-slate-500">运行：</span>
        <select
          value={runId}
          onChange={(event) => setRunId(event.target.value)}
          className="rounded-md border border-surface-border px-2 py-1 text-xs"
        >
          {SAMPLE_RUN_IDS.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-sm text-slate-400">正在加载风险发现…</p>}

      {error && (
        <ErrorState
          title="风险发现不可用"
          message={error instanceof Error ? error.message : "无法获取风险发现数据"}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {meta && <DemoBanner meta={meta} />}

      {findings.length === 0 && !isLoading && !error && (
        <p className="text-sm text-slate-400">暂无风险发现。</p>
      )}

      <div className="space-y-3">
        {findings.map((finding) => (
          <Card key={finding.finding_id} title={finding.finding_id}>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge variant="neutral" className="font-mono">{finding.category}</Badge>
              <span className={cn("rounded-full px-2 py-0.5 font-medium", severityColor[finding.severity])}>
                {finding.severity}
              </span>
              <span className="text-slate-500">检测方法：{finding.detection_method}</span>
              <span className="text-slate-500">评分：{finding.score.toFixed(2)}</span>
              {finding.calibrated ? (
                <Badge variant="ok">已校准</Badge>
              ) : (
                <Badge variant="warn">未校准</Badge>
              )}
              <Badge variant="neutral" className="font-mono">{finding.verification_status}</Badge>
            </div>
            {finding.evidence_ids.length > 0 && (
              <div className="mt-2 text-xs text-slate-600">
                <span className="font-medium">支持证据：</span>
                {finding.evidence_ids.map((id) => (
                  <span key={id} className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono">
                    {id}
                  </span>
                ))}
              </div>
            )}
            {finding.graph_nodes.length > 0 && (
              <div className="mt-1 text-xs text-slate-600">
                <span className="font-medium">关联图谱元素：</span>
                {finding.graph_nodes.map((node) => (
                  <span key={node} className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono">
                    {node}
                  </span>
                ))}
              </div>
            )}
            <p className="mt-2 text-xs text-slate-500">
              <span className="font-medium">尚未证实：</span>
              {finding.unverified}
            </p>
          </Card>
        ))}
      </div>
    </div>
  );
}

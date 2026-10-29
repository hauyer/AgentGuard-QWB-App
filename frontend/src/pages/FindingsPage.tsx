import { useResourceSelection } from "../hooks/use-resource-selection";
import { ResourcePicker } from "../components/shared/resource-picker";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import { cn } from "../utils/cn";

import type { MetaInfo } from "../types/dashboard";


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
  const [runId, setRunId] = useResourceSelection("run_id");
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["findings", runId],
    enabled: Boolean(runId),
    queryFn: ({ signal }) => fetchFindings(runId, signal),
  });

  const findings = data?.items ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <PageHeader
        title="风险发现"
        description="风险等级、支持证据与待验证事项。"
      />

      <ResourcePicker value={runId} onSelect={setRunId} kind="run"/>

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

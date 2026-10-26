import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";

import type { MetaInfo } from "../types/dashboard";

const SAMPLE_RUN_IDS = ["run-qwb-0001"];

interface Hypothesis {
  hypothesis_id: string;
  finding_id: string;
  statement: string;
  rationale: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  needs_verification: string[];
  recommended_action: string;
}

interface HypothesesResponse {
  meta: MetaInfo;
  items: Hypothesis[];
}

async function fetchHypotheses(runId: string, signal?: AbortSignal): Promise<HypothesesResponse> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/hypotheses`, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function HypothesesPage() {
  const [searchParams] = useSearchParams();
  const initialRunId = searchParams.get("run_id") ?? SAMPLE_RUN_IDS[0];
  const [runId, setRunId] = useState(initialRunId);
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["hypotheses", runId],
    queryFn: ({ signal }) => fetchHypotheses(runId, signal),
  });

  const hypotheses = data?.items ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <PageHeader
        title="调查假设"
        description="查看每项风险的支持证据、反对证据与待验证条件。"
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

      {isLoading && <p className="text-sm text-slate-400">正在加载调查假设…</p>}

      {error && (
        <ErrorState
          title="调查假设不可用"
          message={error instanceof Error ? error.message : "无法获取调查假设数据"}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {meta && <DemoBanner meta={meta} />}

      {hypotheses.length === 0 && !isLoading && !error && (
        <p className="text-sm text-slate-400">暂无调查假设。</p>
      )}

      <div className="space-y-3">
        {hypotheses.map((hyp) => (
          <Card key={hyp.hypothesis_id} title={hyp.hypothesis_id}>
            <div className="mb-2 flex items-center gap-2 text-xs">
              <span className="text-slate-500">关联风险：</span>
              <Badge variant="neutral" className="font-mono">{hyp.finding_id}</Badge>
              <span className="text-slate-500">推荐动作：</span>
              <Badge variant="ok">{hyp.recommended_action}</Badge>
            </div>
            <p className="text-sm font-medium text-slate-800">{hyp.statement}</p>
            <p className="mt-1 text-xs text-slate-500">
              <span className="font-medium">提出理由：</span>
              {hyp.rationale}
            </p>
            {hyp.supporting_evidence.length > 0 && (
              <div className="mt-2 text-xs text-slate-600">
                <span className="font-medium">支持证据：</span>
                {hyp.supporting_evidence.map((id) => (
                  <span key={id} className="ml-2 rounded bg-green-50 px-1.5 py-0.5 font-mono text-green-700">
                    {id}
                  </span>
                ))}
              </div>
            )}
            {hyp.contradicting_evidence.length > 0 && (
              <div className="mt-1 text-xs text-slate-600">
                <span className="font-medium">反对证据：</span>
                {hyp.contradicting_evidence.map((id) => (
                  <span key={id} className="ml-2 rounded bg-red-50 px-1.5 py-0.5 font-mono text-red-700">
                    {id}
                  </span>
                ))}
              </div>
            )}
            {hyp.needs_verification.length > 0 && (
              <div className="mt-2 text-xs text-slate-500">
                <span className="font-medium">仍需验证：</span>
                <ul className="ml-4 mt-1 list-disc">
                  {hyp.needs_verification.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}

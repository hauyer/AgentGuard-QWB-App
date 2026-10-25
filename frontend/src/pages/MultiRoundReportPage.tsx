import { useQuery } from "@tanstack/react-query";

import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import type { MetaInfo } from "../types/dashboard";

interface ReportSection {
  title: string;
  content: string;
}

async function fetchReport(runId: string, signal?: AbortSignal): Promise<{ meta: MetaInfo; sections: ReportSection[] }> {
  const res = await fetch(`/api/reports/${encodeURIComponent(runId)}`, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function MultiRoundReportPage() {
  const runId = "run-qwb-0001";
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["multi-round-report", runId],
    queryFn: ({ signal }) => fetchReport(runId, signal),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title="多轮调查报告"
        description="完整调查报告：调查概况、观察环境、风险分析、假设与证据、多轮决策表、预算成本、防御候选、验证状态与研究限制。"
      />

      {isLoading && <p className="text-sm text-slate-400">正在加载报告…</p>}

      {error && (
        <ErrorState
          title="报告不可用"
          message={error instanceof Error ? error.message : "无法获取报告数据"}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {data && (
        <>
          <DemoBanner meta={data.meta} />

          <div className="flex gap-2">
            <button className="rounded-md bg-slate-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700">
              导出 JSON
            </button>
            <button className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
              导出 PDF
            </button>
          </div>

          <Card title="调查概况">
            <div className="text-xs text-slate-600">
              <p>运行 ID：<span className="font-mono">{runId}</span></p>
              <p>场景：sc-qwb-001</p>
              <p>模型版本：agent-suite-2.1</p>
              <p>数据模式：<Badge variant="neutral">{data.meta.data_mode}</Badge></p>
            </div>
          </Card>

          <Card title="观察环境">
            <p className="text-xs text-slate-600">
              多 Agent 协作环境，包含 Agent A（任务发起者）和 Agent B（工具执行者），
              通过工具调用进行交互。观察环境为合成测试场景，不代表真实生产系统。
            </p>
          </Card>

          <Card title="风险分析">
            <ul className="ml-4 list-disc text-xs text-slate-600">
              <li><span className="font-mono">fd-qwb-0001</span>：工具滥用（高风险，观测性）</li>
              <li><span className="font-mono">fd-qwb-0002</span>：提示注入（中风险，干预性）</li>
            </ul>
          </Card>

          <Card title="假设与证据">
            <ul className="ml-4 list-disc text-xs text-slate-600">
              <li><span className="font-mono">hp-qwb-0001</span>：Agent A 被诱导执行越权工具操作（支持证据：ev-qwb-0001, ev-qwb-0002）</li>
              <li><span className="font-mono">hp-qwb-0002</span>：Agent B 接收注入指令（支持证据：ev-qwb-0003）</li>
            </ul>
          </Card>

          <Card title="多轮调查决策表">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="py-2 pr-4">轮次</th>
                    <th className="py-2 pr-4">动作</th>
                    <th className="py-2 pr-4">结果</th>
                    <th className="py-2 pr-4">新增证据</th>
                    <th className="py-2 pr-4">消耗</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-slate-100">
                    <td className="py-2 pr-4">1</td>
                    <td className="py-2 pr-4 font-mono">observe_messages</td>
                    <td className="py-2 pr-4">获取 12 条消息</td>
                    <td className="py-2 pr-4 font-mono">ev-qwb-0001</td>
                    <td className="py-2 pr-4">1 动作 / 12.4s</td>
                  </tr>
                  <tr className="border-b border-slate-100">
                    <td className="py-2 pr-4">2</td>
                    <td className="py-2 pr-4 font-mono">intervention_test</td>
                    <td className="py-2 pr-4">注入测试成功</td>
                    <td className="py-2 pr-4 font-mono">ev-qwb-0002, ev-qwb-0003</td>
                    <td className="py-2 pr-4">1 动作 / 34.9s</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="预算与成本">
            <p className="text-xs text-slate-600">
              使用 2/5 动作，47.3/120 秒，3/10 模型调用。停止原因：证据充分（evidence_sufficient）。
            </p>
          </Card>

          <Card title="防御候选">
            <p className="text-xs text-slate-600">
              候选防御策略：白名单阻断（whitelist-block）。当前为预览状态，未实际执行。
              实际防御执行能力受限于 WARDEN 干预验证状态。
            </p>
          </Card>

          <Card title="验证状态">
            <p className="text-xs text-slate-600">
              证据等级：观测性（observational）+ 干预性（interventional）。
              未达到因果验证（causal_validated）级别。
            </p>
          </Card>

          <Card title="研究限制">
            <ul className="ml-4 list-disc text-xs text-slate-500">
              <li>单一合成场景，样本数为 1，统计显著性不足</li>
              <li>观测性发现不构成因果结论</li>
              <li>防御效果未经验证</li>
              <li>本报告为回放数据，不代表实时运行</li>
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}

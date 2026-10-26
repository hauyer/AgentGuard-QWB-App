import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuthStore } from "../stores/auth-store";
import { useEvidence } from "../hooks/use-evidence";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import { EvidenceLevelBadge } from "../components/shared/evidence-level-badge";
import { SourceBadge } from "../components/shared/source-badge";
import { VerificationBadge } from "../components/shared/verification-badge";
import type { EvidenceItem } from "../types/evidence";
import { cn } from "../utils/cn";

const SAMPLE_REQUEST_IDS = ["inv-qwb-0001", "inv-qwb-0005"];

export function EvidencePage() {
  const role = useAuthStore((state) => state.role);
  const [searchParams] = useSearchParams();
  const initialRequestId = searchParams.get("request_id") ?? SAMPLE_REQUEST_IDS[0];
  const [requestId, setRequestId] = useState(initialRequestId);
  const { data, isLoading, error, refetch, isFetching } = useEvidence(requestId);

  const evidence = data?.evidence;
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <PageHeader
        title="证据分析"
        description="按来源、证据等级和验证状态浏览。"
      />

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-slate-500">调查：</span>
        <select
          value={requestId}
          onChange={(event) => setRequestId(event.target.value)}
          className="rounded-md border border-surface-border px-2 py-1 text-xs"
        >
          {SAMPLE_REQUEST_IDS.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-sm text-slate-400">正在加载证据…</p>}

      {error && (
        <ErrorState
          title="证据不可用"
          message={error instanceof Error ? error.message : "无法获取证据数据"}
          code={(error as { code?: string }).code}
          requestId={(error as { requestId?: string | null }).requestId}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {data && meta && <DemoBanner meta={meta} />}

      {evidence && (
        <>
          <Card title={`调查 ${evidence.request_id ?? requestId}`}>
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
              <SourceBadge source={meta?.data_mode === "live" ? "agentguard" : (meta?.fixture_id ?? "demo")} mode={meta?.data_mode} />
              <span>
                工作流状态：<Badge variant="neutral">{evidence.workflow_status ?? "—"}</Badge>
              </span>
              <span>
                运行状态：<Badge variant="neutral">{evidence.run_status ?? "—"}</Badge>
              </span>
            </div>
            {evidence.limitations.map((limitation) => (
              <p key={limitation} className="mt-2 text-xs text-amber-700">
                ⚠ {limitation}
              </p>
            ))}
          </Card>

          <div className="space-y-3">
            {evidence.items.map((item) => (
              <EvidenceCard key={item.evidence_id} item={item} />
            ))}
            {evidence.items.length === 0 && (
              <p className="text-sm text-slate-400">该调查暂无证据记录。</p>
            )}
          </div>
        </>
      )}

      <p className="text-[11px] text-slate-400">
        当前角色：<span className="font-mono">{role ?? "未登录"}</span>。观测性证据不会被标注为“因果路径已确认”；
        工件引用仅展示元信息，不尝试访问本地文件 URI。
      </p>
    </div>
  );
}

function EvidenceCard({ item }: { item: EvidenceItem }) {
  const isCausal = item.evidence_level === "causal_validated";
  return (
    <Card title={item.evidence_id} key={item.evidence_id}>
      <div className="flex flex-wrap items-center gap-2">
        <EvidenceLevelBadge level={item.evidence_level} />
        <VerificationBadge status={item.verification_status} />
        {item.source_system && <SourceBadge source={item.source_system} />}
        <Badge variant="neutral">{item.evidence_type ?? "—"}</Badge>
      </div>

      <dl className="mt-3 grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
        <Detail label="调查假设" value={item.hypothesis ?? "—"} wide />
        <Detail label="目标" value={`${item.target_type ?? "?"}:${item.target_ref ?? "—"}`} mono />
        <Detail label="内核运行 ID" value={item.warden_run_id ?? "—"} mono />
        <Detail label="计划 ID" value={item.warden_plan_id ?? "—"} mono />
        <Detail label="风险类型" value={item.risk_type ?? "—"} />
        <Detail label="模型版本" value={item.model_version ?? "—"} />
        <Detail label="置信度" value={item.confidence == null ? "—" : String(item.confidence)} />
        <Detail label="证据类型" value={item.evidence_type ?? "—"} />
      </dl>

      <div className="mt-3 space-y-1 text-xs">
        <dt className="text-slate-400">工件引用（不提供可下载工件，仅展示引用）</dt>
        <dd className="font-mono text-slate-600">
          {item.artifact_refs.length === 0 ? "（空）" : item.artifact_refs.join(", ")}
        </dd>
      </div>

      <div className="mt-3 space-y-1 text-xs">
        <dt className="text-slate-400">局限性</dt>
        {item.limitations.map((limitation) => (
          <dd key={limitation} className="text-amber-700">
            ⚠ {limitation}
          </dd>
        ))}
      </div>

      {item.causal_validation && (
        <div
          className={cn(
            "mt-3 rounded-md border p-3 text-xs",
            isCausal ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50",
          )}
        >
          <p className="font-medium text-slate-700">
            因果验证：{item.causal_validation.method ?? "—"}（{item.causal_validation.status ?? "—"}）
          </p>
          {item.causal_validation.note && <p className="mt-1 text-slate-600">{item.causal_validation.note}</p>}
          {!isCausal && <p className="mt-1 text-amber-700">该结果不是 causal_validated，不得视为因果路径已确认。</p>}
        </div>
      )}
    </Card>
  );
}

function Detail({ label, value, mono, wide }: { label: string; value: string; mono?: boolean; wide?: boolean }) {
  return (
    <div className={wide ? "sm:col-span-2" : undefined}>
      <dt className="text-slate-400">{label}</dt>
      <dd className={mono ? "font-mono text-slate-700" : "text-slate-700"}>{value}</dd>
    </div>
  );
}

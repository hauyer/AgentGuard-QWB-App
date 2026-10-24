import "@xyflow/react/dist/style.css";
import { toPng } from "html-to-image";

import { useCallback, useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Edge as FlowEdge,
  type Node as FlowNode,
  type NodeProps,
} from "@xyflow/react";

import { useAuthStore } from "../stores/auth-store";
import { useGraph } from "../hooks/use-graph";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Drawer } from "../components/ui/drawer";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import type { GraphEdge, GraphNode, GraphNodeType } from "../types/graph";
import { cn } from "../utils/cn";

interface GraphNodeData {
  label: string;
  risk: string;
  source_id: string;
  timestamp?: string | null;
  kind: GraphNodeType;
  [key: string]: unknown;
}

const NODE_STYLE: Record<GraphNodeType, { bg: string; ring: string }> = {
  agent: { bg: "bg-sky-50", ring: "ring-sky-300" },
  tool: { bg: "bg-amber-50", ring: "ring-amber-300" },
  model: { bg: "bg-violet-50", ring: "ring-violet-300" },
  invocation: { bg: "bg-emerald-50", ring: "ring-emerald-300" },
  external_resource: { bg: "bg-rose-50", ring: "ring-rose-300" },
};

const NODE_LABEL: Record<GraphNodeType, string> = {
  agent: "Agent",
  tool: "工具",
  model: "模型",
  invocation: "调用",
  external_resource: "外部资源",
};

const EDGE_COLOR: Record<GraphEdge["type"], string> = {
  message: "#0ea5e9",
  invocation: "#f59e0b",
  result: "#10b981",
};

const RISK_TONE: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-slate-100 text-slate-600",
};

function GraphNodeView({ data }: NodeProps<FlowNode<GraphNodeData>>) {
  const style = NODE_STYLE[data.kind];
  return (
    <div className={cn("rounded-lg px-3 py-2 ring-2", style.bg, style.ring)}>
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{NODE_LABEL[data.kind]}</span>
        <Badge variant="neutral" className={cn("px-1.5 text-[10px]", RISK_TONE[data.risk] ?? RISK_TONE.low)}>
          {data.risk}
        </Badge>
      </div>
      <div className="mt-0.5 text-xs font-medium text-slate-800">{data.label}</div>
      <div className="font-mono text-[10px] text-slate-400">{data.source_id}</div>
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  );
}

const nodeTypes = { graphNode: GraphNodeView };

/** Deterministic layout on a 5x5 grid derived from the node id hash. */
function layoutPosition(id: string): { x: number; y: number } {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  const col = hash % 5;
  const row = Math.floor(hash / 5) % 5;
  return { x: 60 + col * 260, y: 60 + row * 140 };
}

const RISK_ORDER = ["low", "medium", "high"];

function InteractionGraphView() {
  const role = useAuthStore((state) => state.role);
  const { data, isLoading, error, refetch, isFetching } = useGraph(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [hiddenTypes, setHiddenTypes] = useState<Set<GraphNodeType>>(new Set());
  const [minRisk, setMinRisk] = useState(0); // 0=all,1=low,2=medium,3=high
  const [maxTs, setMaxTs] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const graph = data?.graph;

  const timestamps = useMemo(() => {
    if (!graph) return [];
    const values = [...graph.nodes.map((n) => n.timestamp), ...graph.edges.map((e) => e.timestamp)].filter(
      (value): value is string => Boolean(value),
    );
    return [...new Set(values)].sort();
  }, [graph]);

  const filterPasses = useCallback(
    (risk: string, ts?: string | null, type?: GraphNodeType) => {
      const riskLevel = RISK_ORDER.indexOf(risk);
      if (riskLevel < minRisk) return false;
      if (type && hiddenTypes.has(type)) return false;
      if (maxTs && (!ts || ts > maxTs)) return false;
      return true;
    },
    [minRisk, hiddenTypes, maxTs],
  );

  const path = graph?.candidate_paths.find((p) => p.id === selectedPath) ?? null;

  const nodes: FlowNode<GraphNodeData>[] = useMemo(
    () => {
      const pathNodeSet = new Set(path?.node_ids ?? []);
      return (graph?.nodes ?? [])
        .filter((node) => filterPasses(node.risk, node.timestamp, node.type))
        .map((node) => ({
          id: node.id,
          type: "graphNode",
          position: layoutPosition(node.id),
          data: {
            label: node.label,
            risk: node.risk,
            source_id: node.source_id,
            timestamp: node.timestamp,
            kind: node.type,
          },
          className: pathNodeSet.has(node.id) ? "!ring-2 !ring-brand-600" : undefined,
        }));
    },
    [graph, filterPasses, path],
  );

  const edges: FlowEdge[] = useMemo(
    () => {
      const pathEdgeSet = new Set(path?.edge_ids ?? []);
      return (graph?.edges ?? [])
        .filter((edge) => filterPasses(edge.risk, edge.timestamp))
        .map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.type,
          style: { stroke: EDGE_COLOR[edge.type], strokeWidth: pathEdgeSet.has(edge.id) ? 3 : 1.5 },
          className: pathEdgeSet.has(edge.id) ? "!stroke-brand-600" : undefined,
          data: edge,
        }));
    },
    [graph, filterPasses, path],
  );

  const onEdgeClick = (_: unknown, edge: FlowEdge) => setSelectedEdge(edge.data as unknown as GraphEdge);
  const onNodeClick = (_: unknown, node: FlowNode) =>
    setSelectedNode((graph?.nodes ?? []).find((n) => n.id === node.id) ?? null);

  const exportPng = async () => {
    if (!graph) return;
    setExporting(true);
    try {
      // find the React Flow viewport element inside the canvas container
      const container = document.querySelector<HTMLElement>(".react-flow__viewport");
      if (!container) throw new Error("图谱画布尚未就绪");
      const dataUrl = await toPng(container, {
        backgroundColor: "#ffffff",
        width: 1600,
        height: 1000,
        pixelRatio: 2,
      });
      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = `interaction-graph-${graph.scenario_id ?? "sample"}.png`;
      link.click();
    } finally {
      setExporting(false);
    }
  };

  if (isLoading) return <PageHeader title="交互图谱" description="正在加载图谱样本…" />;

  if (error || !data) {
    return (
      <div className="space-y-4">
        <PageHeader title="交互图谱" description="多 Agent 通信与工具调用关系" />
        <ErrorState
          title="图谱不可用"
          message={error instanceof Error ? error.message : "无法获取图谱数据"}
          code={(error as { code?: string }).code}
          requestId={(error as { requestId?: string | null }).requestId}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="交互图谱"
        description="Agent ↔ 工具 ↔ 模型通信。所有节点与边均带来源 ID，可追溯到录制样本。"
        actions={
          <Button variant="secondary" onClick={() => void exportPng()} disabled={exporting}>
            {exporting ? "导出中…" : "导出 PNG"}
          </Button>
        }
      />

      <DemoBanner meta={data.meta} />

      {graph?.not_provable?.map((note) => (
        <p key={note} className="text-xs text-amber-700">
          ⚠ {note}
        </p>
      ))}

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-500">节点类型：</span>
          {(Object.keys(NODE_STYLE) as GraphNodeType[]).map((type) => (
            <button
              key={type}
              type="button"
              onClick={() =>
                setHiddenTypes((previous) => {
                  const next = new Set(previous);
                  if (next.has(type)) next.delete(type);
                  else next.add(type);
                  return next;
                })
              }
              className={cn(
                "rounded-full border px-2 py-0.5 text-[11px]",
                hiddenTypes.has(type) ? "border-surface-border text-slate-300" : "border-slate-300 text-slate-700",
              )}
            >
              {NODE_LABEL[type]}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-500">最低风险：</span>
          <select
            value={minRisk}
            onChange={(event) => setMinRisk(Number(event.target.value))}
            className="rounded-md border border-surface-border px-2 py-1 text-xs"
          >
            <option value={0}>全部</option>
            <option value={1}>low</option>
            <option value={2}>medium</option>
            <option value={3}>high</option>
          </select>
        </div>
        {timestamps.length > 1 && (
          <div className="flex min-w-56 items-center gap-2">
            <span className="text-xs text-slate-500">时间回放</span>
            <input
              type="range"
              min={0}
              max={timestamps.length - 1}
              value={maxTs ? timestamps.indexOf(maxTs) : timestamps.length - 1}
              onChange={(event) => {
                const index = Number(event.target.value);
                setMaxTs(index === timestamps.length - 1 ? null : timestamps[index]);
              }}
              className="w-full"
            />
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-500">候选路径：</span>
        <button
          type="button"
          onClick={() => setSelectedPath(null)}
          className={cn(
            "rounded-full border px-3 py-1 text-xs",
            selectedPath === null ? "border-brand-600 bg-brand-50 text-brand-700" : "border-surface-border text-slate-600",
          )}
        >
          全部
        </button>
        {graph?.candidate_paths.map((candidate) => (
          <button
            key={candidate.id}
            type="button"
            onClick={() => setSelectedPath(candidate.id)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs",
              selectedPath === candidate.id
                ? "border-brand-600 bg-brand-50 text-brand-700"
                : "border-surface-border text-slate-600 hover:bg-surface-muted",
            )}
          >
            {candidate.label}
          </button>
        ))}
      </div>

      {path && (
        <Card title="候选路径详情">
          <div className="space-y-1 text-xs text-slate-600">
            <p>
              路径 <span className="font-mono">{path.id}</span> · 风险{" "}
              <Badge variant="neutral">{path.risk}</Badge>
            </p>
            <p>
              节点：<span className="font-mono text-slate-700">{path.node_ids.join(" → ")}</span>
            </p>
            <p>
              关联证据引用：
              <span className="font-mono text-brand-700">{path.evidence_refs.join(", ")}</span>
            </p>
          </div>
        </Card>
      )}

      <div className="h-[560px] overflow-hidden rounded-lg border border-surface-border bg-white shadow-sm">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onEdgeClick={onEdgeClick}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} size={1} />
          <Controls />
          <MiniMap pannable zoomable />
        </ReactFlow>
      </div>

      <Drawer open={selectedEdge !== null} onClose={() => setSelectedEdge(null)} title="边（消息/调用）元数据">
        {selectedEdge && (
          <dl className="space-y-2 text-xs">
            <Detail label="边 ID" value={selectedEdge.id} mono />
            <Detail label="类型" value={selectedEdge.type} />
            <Detail label="来源节点" value={selectedEdge.source} mono />
            <Detail label="目标节点" value={selectedEdge.target} mono />
            <Detail label="消息 ID" value={selectedEdge.message_id ?? "—"} mono />
            <Detail label="来源 ID" value={selectedEdge.source_id} mono />
            <Detail label="风险" value={selectedEdge.risk} />
            <Detail label="时间" value={selectedEdge.timestamp ?? "—"} mono />
            {selectedEdge.metadata && (
              <div>
                <dt className="text-slate-400">元数据</dt>
                <dd className="mt-1 rounded-md bg-surface-muted p-2 font-mono text-[11px] text-slate-700">
                  {JSON.stringify(selectedEdge.metadata, null, 2)}
                </dd>
              </div>
            )}
          </dl>
        )}
      </Drawer>

      <Drawer open={selectedNode !== null} onClose={() => setSelectedNode(null)} title="节点信息">
        {selectedNode && (
          <dl className="space-y-2 text-xs">
            <Detail label="节点 ID" value={selectedNode.id} mono />
            <Detail label="类型" value={selectedNode.type} />
            <Detail label="名称" value={selectedNode.label} />
            <Detail label="来源 ID" value={selectedNode.source_id} mono />
            <Detail label="风险" value={selectedNode.risk} />
            <Detail label="时间" value={selectedNode.timestamp ?? "—"} mono />
          </dl>
        )}
      </Drawer>

      <p className="text-[11px] text-slate-400">
        当前角色：<span className="font-mono">{role ?? "未登录"}</span>。Live 模式因 QWB-INT-001 无法获取消息级图谱；
        本页演示数据为 SYNTHETIC 样例，不构成真实运行记录。
      </p>
    </div>
  );
}

export function InteractionGraphPage() {
  return (
    <ReactFlowProvider>
      <InteractionGraphView />
    </ReactFlowProvider>
  );
}

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-slate-400">{label}</dt>
      <dd className={mono ? "font-mono text-slate-700" : "text-slate-700"}>{value}</dd>
    </div>
  );
}

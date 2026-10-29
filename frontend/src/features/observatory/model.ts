export interface ExperimentEvent {
  schema_version: "stego.event/1"; event_id: string; run_id: string; study_id: string; arm_id: string;
  seq: number; at_utc: string; type: string; provenance: "observed" | "derived" | "planned" | "demo";
  actor_id?: string | null; source_agent_id?: string | null; target_agent_id?: string | null;
  message_id?: string | null; evidence_refs: string[]; data: Record<string, string | number | boolean | null>;
}
export interface AgentView {
  id: string; label: string; role: string; status: string; source_event_ids: string[];
}
export interface MessageView {
  id: string; source: string; target: string; message_ids: string[]; channel_type: string;
  delivered_count: number; blocked_count: number; source_event_ids: string[];
}
export interface ProbeView {
  id: string; agent_id: string; associated_edge_id?: string | null; value: number | null;
  threshold?: number | null; target_layer?: number | null; token_policy?: string | null;
  label_semantics: string; evaluation_split?: string | null; claim_level: string;
  evidence_refs: string[]; source_event_ids?: string[];
  threshold_passed?: boolean | null; detection_status?: string; threshold_source?: string | null;
  probability_calibrated?: boolean; probe_model_version?: string | null; measurement_phase?: string | null;
}
export interface GraphView {
  schema_version: "stego.graph/1"; study_id: string; run_id: string | null; track: string;
  state: string; nodes: AgentView[]; communication_edges: MessageView[]; probe_evidence: ProbeView[];
  interventions: { id: string; kind: string; execution_state: string; target: { type: string; id: string }; details?:Record<string,unknown> }[];
  evidence_status: string; limitations: string[];
}
export interface ExperimentView {
  schema_version: "stego.visualization/1"; data_mode: string; origin_mode: string; workflow_id: string;
  status: string; graph: GraphView; events: ExperimentEvent[]; last_seq: number;
  metrics: Record<string, {value: number | null; denominator: number}>;
  artifacts: {artifact_id: string; sha256: string}[]; unavailable_reason: string | null; limitations: string[];
}
export interface ComparisonView {
  status: string; blockers: string[]; limitations?: string[];
  batch_id?: string; replicate_id?: string|null; research_validity?: string;
  research_limitations?: string[]; selected_runs?:{arm_id:string;workflow_id:string;run_id:string|null}[];
  baseline_srr?:{value:number;successes:number;planned:number;wilson_95_ci:number[]};
  multiplicity_method?:string;
  adjusted_pvalues?:Record<string,{p_value:number;adjusted_p_value:number;reject_at_0_05:boolean}>;
  arms: {arm_id: string; status: string; sample_count?: number; missing_count?: number;
    baseline_run_id?: string; treatment_run_id?: string; blockers: string[];
    metrics?: Record<string, {value: number | null; denominator: number}>;
    effects?: Record<string, {mean_treatment_minus_control: number; cluster_bootstrap_95_ci: number[]} | null>;
  }[];
}
const eventTypes = new Set(["agent_started", "message_sent", "message_delivered", "message_blocked", "message_replaced",
  "probe_observed", "intervention_planned", "intervention_applied", "intervention_failed", "receiver_decoded",
  "task_evaluated", "run_completed", "run_failed"]);

/** Validate the public boundary before React Flow consumes any graph/event IDs. */
export function parseExperimentView(value: unknown): ExperimentView {
  if (!value || typeof value !== "object") throw new Error("实验视图不是有效对象。");
  const view = value as ExperimentView;
  if (view.schema_version !== "stego.visualization/1" || view.graph?.schema_version !== "stego.graph/1"
    || !Array.isArray(view.graph.nodes) || !Array.isArray(view.graph.communication_edges)
    || !Array.isArray(view.graph.probe_evidence) || !Array.isArray(view.events)
    || !Array.isArray(view.graph.interventions) || !Array.isArray(view.artifacts)
    || !Array.isArray(view.limitations) || typeof view.status!=="string"
    || !Number.isSafeInteger(view.last_seq) || view.last_seq<0) throw new Error("实验视图合同不兼容。");
  const strings=(items:unknown):items is string[]=>Array.isArray(items)&&items.every(item=>typeof item==="string");
  const id=(item:unknown):item is string=>typeof item==="string"&&item.length>0;
  if(view.graph.nodes.some(node=>!node||!id(node.id)||typeof node.label!=="string"||typeof node.role!=="string"
    ||!strings(node.source_event_ids))||view.graph.communication_edges.some(edge=>!edge||!id(edge.id)
      ||!strings(edge.message_ids)||!Number.isSafeInteger(edge.delivered_count)||edge.delivered_count<0
      ||!Number.isSafeInteger(edge.blocked_count)||edge.blocked_count<0)
    ||view.graph.probe_evidence.some(probe=>!probe||!id(probe.id)||!id(probe.agent_id)||!strings(probe.evidence_refs)
      ||(probe.value!==null&&!Number.isFinite(probe.value)))
    ||view.graph.interventions.some(item=>!item||!id(item.id)||!id(item.target?.id)||typeof item.kind!=="string"))throw new Error("图谱字段不完整。");
  const nodes = new Set(view.graph.nodes.map((node) => node.id));
  if (nodes.size !== view.graph.nodes.length || view.graph.communication_edges.some((edge) =>
    !nodes.has(edge.source) || !nodes.has(edge.target) || !Array.isArray(edge.source_event_ids))) throw new Error("图谱引用不完整。");
  let previous = 0;
  const ids=new Set<string>();
  for (const event of view.events) {
    if (!event || event.schema_version !== "stego.event/1" || !eventTypes.has(event.type)
      || event.seq <= previous || !Number.isInteger(event.seq) || !Array.isArray(event.evidence_refs)
      || !id(event.event_id) || ids.has(event.event_id) || !event.data || typeof event.data!=="object"
      || event.study_id !== view.graph.study_id || event.run_id !== view.graph.run_id
      || !Number.isFinite(Date.parse(event.at_utc))) throw new Error("事件类型、顺序或运行来源不兼容。");
    ids.add(event.event_id);
    previous = event.seq;
  }
  if(previous!==view.last_seq||!view.metrics||Object.values(view.metrics).some(metric=>!metric
    ||!Number.isSafeInteger(metric.denominator)||metric.denominator<0
    ||(metric.value!==null&&(!Number.isFinite(metric.value)||metric.denominator===0))))throw new Error("指标或事件游标不兼容。");
  return view;
}

export function parseComparisonView(value:unknown):ComparisonView {
  if(!value||typeof value!=="object")throw new Error("配对结果不是有效对象。");
  const result=value as ComparisonView&{schema_version:string};
  if(result.adjusted_pvalues&&Object.values(result.adjusted_pvalues).some(p=>!p||
    !Number.isFinite(p.p_value)||p.p_value<0||p.p_value>1||!Number.isFinite(p.adjusted_p_value)||
    p.adjusted_p_value<0||p.adjusted_p_value>1||typeof p.reject_at_0_05!=="boolean"))throw new Error("校正统计结果合同不兼容。");
  if(!["stego.comparison/1","stego.comparison/2"].includes(result.schema_version)||!Array.isArray(result.arms)||!Array.isArray(result.blockers)
    ||result.arms.some(row=>!row||typeof row.arm_id!=="string"||typeof row.status!=="string"
      ||!Array.isArray(row.blockers)||Object.values(row.metrics??{}).some(metric=>!metric
        ||!Number.isSafeInteger(metric.denominator)||metric.denominator<0
        ||(metric.value!==null&&!Number.isFinite(metric.value)))
      ||Object.values(row.effects??{}).some(effect=>effect!==null&&(!Number.isFinite(effect.mean_treatment_minus_control)
        ||!Array.isArray(effect.cluster_bootstrap_95_ci)||effect.cluster_bootstrap_95_ci.length!==2
        ||!effect.cluster_bootstrap_95_ci.every(Number.isFinite)))))throw new Error("配对结果合同不兼容。");
  return result;
}

/** Cursor projection never fabricates a message from a Probe observation. */
export function atSequence(view: ExperimentView, seq: number): GraphView {
  const seen = new Set(view.events.filter((event) => event.seq <= seq).map((event) => event.event_id));
  const nodes = view.graph.nodes.filter((node) => node.source_event_ids.some((id) => seen.has(id))).map((node) => ({
    ...node, status: view.events.some(event=>event.seq<=seq&&event.type==="run_failed"&&event.actor_id===node.id)?"failed":view.events.some((event) => event.seq <= seq && event.type === "intervention_applied"
      && event.data.kind === "agent_isolation" && event.data.target === node.id) ? "isolated" : "active",
  }));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const events = view.events.filter((event) => event.seq <= seq);
  return {...view.graph, nodes, communication_edges: view.graph.communication_edges.filter((edge) =>
    nodeIds.has(edge.source) && nodeIds.has(edge.target) && edge.source_event_ids.some((id) => seen.has(id))).map((edge) => ({
      ...edge, delivered_count: events.filter((event) => event.type === "message_delivered" && edge.message_ids.includes(event.message_id ?? "")).length,
      blocked_count: events.filter((event) => event.type === "message_blocked" && edge.message_ids.includes(event.message_id ?? "")).length,
    })), probe_evidence: view.graph.probe_evidence.filter((probe) => seen.has(probe.id)),
    interventions: view.graph.interventions.filter((item) => seen.has(item.id))};
}

/** Frozen label threshold, never a calibrated covert-channel probability. */
export function probeThreshold(probe: ProbeView): boolean|null {
  return probe.value!==null&&probe.threshold!=null&&Number.isFinite(probe.threshold)
    ?probe.value>=probe.threshold:null;
}

export function eventSelection(event: ExperimentEvent): string|null {
  return event.source_agent_id&&event.target_agent_id?`${event.source_agent_id}->${event.target_agent_id}`
    :event.actor_id||null;
}

export const METHOD_NAMES: Record<string, string> = {baseline: "无干预基线", agent_isolation: "Agent 隔离",
  message_block: "消息阻断", message_replace: "消息替换", leace: "LEACE 表示擦除", activation_patch: "Activation Patching",
  sham: "无操作对照", random_erasure: "随机等秩擦除", irrelevant: "无关位置对照"};

export const METRIC_NAMES:Record<string,string>={SRR_ITT:"秘密恢复率（ITT）",SRR_EXECUTED:"Receiver 执行后的恢复率",
  INVERTED_READOUT_SRR_ITT:"反转二元读出的恢复率（诊断）",CARRIER_VALID_RATE:"载体格式有效率",RECEIVER_INPUT_NOVELTY_RATE:"独立模型输入覆盖率",BER:"合法比特错误率",UTILITY_COLLABORATIVE:"同路径协作任务效用",UTILITY_INDEPENDENT:"独立辅助读出",
  NORMAL_UTILITY:"独立辅助读出（兼容指标）",EXECUTION_SUCCESS_RATE:"执行成功率",CARRIER_DELIVERY_RATE:"载体交付率",
  SRR_NO_CARRIER:"无有效载体时的猜测恢复率",SRR_VALID_CARRIER:"有效载体条件下的恢复率"};

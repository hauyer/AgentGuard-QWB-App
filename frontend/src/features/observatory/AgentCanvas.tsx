import "@xyflow/react/dist/style.css";
import { useMemo } from "react";
import { Background, Controls, Handle, Position, ReactFlow, MarkerType, type NodeProps, type Node, type Edge } from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import type { AgentView, GraphView } from "./model";

type AgentData = {agent: AgentView; selectedAgent: boolean; preview: string; applied: string[]; [key:string]: unknown};
function AgentNode({ data }: NodeProps<Node<AgentData>>) {
  return <div className={`observatory-node ${data.selectedAgent?"is-selected":""} ${data.agent.status==='isolated'||data.preview==='agent_isolation'?"is-isolated":""} ${data.preview==='leace'||data.applied.includes('leace')?"has-erasure":""}`}>
    <Handle type="target" position={Position.Left}/><div className={`agent-mark role-${data.agent.role}`}>{data.agent.label.slice(0,1)}</div>
    <div><strong>{data.agent.label}</strong><small>{data.preview?"预览 / 未运行":data.agent.status==='isolated'?"已隔离":data.applied.includes('leace')?"LEACE · 已应用":data.applied.includes('activation_patch')?"Patch · 已应用":"运行观测"}</small></div>
    {(data.preview==='activation_patch'||data.applied.includes('activation_patch'))&&<span className="patch-glyph">＋</span>}
    <Handle type="source" position={Position.Right}/>
  </div>;
}
const nodeTypes = {agent:AgentNode};

export function AgentCanvas({ graph, layoutGraph, selected, onSelect, probeLayer, messageLayer, preview, target, playing, search }: {
  graph: GraphView; layoutGraph: GraphView; selected:string;onSelect:(id:string)=>void;probeLayer:boolean;messageLayer:boolean;
  preview:string;target:string;playing:boolean;search:string;
}) {
  const positions = useMemo(()=>{
    const layout = new dagre.graphlib.Graph().setDefaultEdgeLabel(()=>({}));
    layout.setGraph({rankdir:"LR",nodesep:65,ranksep:100,marginx:45,marginy:45});
    layoutGraph.nodes.forEach(node=>layout.setNode(node.id,{width:162,height:64}));
    layoutGraph.communication_edges.forEach(edge=>layout.setEdge(edge.source,edge.target));
    dagre.layout(layout);
    return new Map(layoutGraph.nodes.map(node=>[node.id,{x:layout.node(node.id).x,y:layout.node(node.id).y}]));
  },[layoutGraph]);
  const nodes: Node<AgentData>[] = graph.nodes.map(agent=>({id:agent.id,type:"agent",position:positions.get(agent.id)??{x:0,y:0},
    data:{agent,selectedAgent:selected===agent.id,preview:target===agent.id?preview:"",
      applied:graph.interventions.filter(item=>item.target.id===agent.id&&item.execution_state==='applied').map(item=>item.kind)},
    style:{opacity:search&&!agent.label.toLowerCase().includes(search.toLowerCase())?.28:1}}));
  const edges:Edge[] = messageLayer ? graph.communication_edges.map(edge=>{
    const highlighted=probeLayer&&graph.probe_evidence.some(p=>p.associated_edge_id===edge.id);
    const isTarget=target===edge.id;
    const blocked=edge.blocked_count>0||(isTarget&&preview==='message_block');
    return {id:edge.id,source:edge.source,target:edge.target,animated:playing&&!blocked&&edge.delivered_count>0,
      label:isTarget&&preview==='message_block'?"⊘ 阻断预览 / 未运行":edge.blocked_count>0?"⊘ 已阻断":isTarget&&preview==='message_replace'?"⇄ 替换预览 / 未运行":graph.interventions.some(item=>item.kind==='message_replace'&&item.target.id===edge.id&&item.execution_state==='applied')?"⇄ 已替换":highlighted?"消息 · Probe 关联":"消息",
      markerEnd:{type:MarkerType.ArrowClosed,color:blocked?"#f17f86":highlighted?"#ba9cff":"#48c4d4"},
      style:{stroke:blocked?"#f17f86":highlighted?"#ba9cff":"#48c4d4",strokeWidth:selected===edge.id?3:1.6,
        strokeDasharray:blocked?"7 6":edge.delivered_count===0?"4 5":undefined},
      labelStyle:{fill:blocked?"#f9a5ac":"#b5c7da",fontSize:10},labelBgStyle:{fill:"#132238",fillOpacity:.95},labelBgPadding:[7,5]};
  }):[];
  return <div className="agent-canvas" role="region" aria-label="Agent 通信图谱">
    <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={.25} maxZoom={2}
      onNodeClick={(_,node)=>onSelect(node.id)} onEdgeClick={(_,edge)=>onSelect(edge.id)}
      proOptions={{hideAttribution:false}} colorMode="dark" nodesDraggable>
      <Background color="#26384c" gap={28} size={1}/><Controls showInteractive/>
    </ReactFlow>
    {!nodes.length&&<div className="canvas-empty"><span>◎</span><strong>尚无可绘制的通信事实</strong><p>M 轨道采集不生成 Sender–Receiver 消息边。<br/>选择真实 S 运行，或单独进入 DEMO 预览。</p></div>}
    <div className="canvas-legend"><span>━ 实际通信</span><span className="violet">┄ Probe 线性证据</span><span className="coral">⊘ 阻断</span></div>
  </div>;
}

import "@xyflow/react/dist/style.css";
import { useEffect, useMemo } from "react";
import { Background, Controls, Handle, Position, ReactFlow, MarkerType, BaseEdge, getBezierPath,
  useReactFlow, useStore, getViewportForBounds,
  type Rect, type EdgeProps, type NodeProps, type Node, type Edge } from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import { probeThreshold, type AgentView, type GraphView } from "./model";

type AgentData = {agent:AgentView; selectedAgent:boolean; preview:string; applied:string[]; foldedFour:boolean; [key:string]:unknown};
function AgentNode({data}:NodeProps<Node<AgentData>>) {
  const isolated=data.agent.status==="isolated"||data.preview==="agent_isolation";
  const incoming=data.foldedFour?(data.agent.id==="sender"?Position.Top:data.agent.id==="receiver"?Position.Right:Position.Left):Position.Left;
  const outgoing=data.foldedFour?(data.agent.id==="data_agent"?Position.Bottom:data.agent.id==="sender"?Position.Left:Position.Right):Position.Right;
  return <div className={`observatory-node ${data.selectedAgent?"is-selected":""} ${isolated?"is-isolated":""} ${data.agent.status==="failed"?"is-failed":""} ${data.preview==="leace"||data.applied.includes("leace")?"has-erasure":""}`}>
    <Handle type="target" position={incoming}/><div className={`agent-mark role-${data.agent.role}`}>{isolated?"⊘":data.agent.label.slice(0,1)}</div>
    <div><strong>{data.agent.label}</strong><small>{data.preview?"预览 / 未运行":isolated?"已隔离":data.agent.status==="failed"?"执行失败":data.applied.includes("leace")?"LEACE · 已应用":data.applied.includes("activation_patch")?"Patch · 已应用":"运行观测"}</small></div>
    {(data.preview==="activation_patch"||data.applied.includes("activation_patch"))&&<span className="patch-glyph">＋</span>}
    <Handle type="source" position={outgoing}/>
  </div>;
}
type EvidenceData = {observed:boolean; passed:boolean; blocked:boolean; caption:string; probeCount:number; passedCount:number; [key:string]:unknown};
function EvidenceEdge(props:EdgeProps<Edge<EvidenceData>>) {
  const [path,x,y]=getBezierPath(props);
  const [overlay]=getBezierPath({...props,sourceY:props.sourceY-9,targetY:props.targetY-9});
  const data=props.data!;
  return <>
    <BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} style={props.style}/>
    {data.observed&&<path data-testid="probe-overlay" d={overlay} fill="none" stroke={data.passed?"#f3b45a":"#ba9cff"} strokeWidth={2} strokeDasharray="3 5" pointerEvents="none"/>}
    {data.observed&&<text x={x} y={y-54} textAnchor="middle" fill={data.passed?"#f3b45a":"#ba9cff"} fontSize={12}>Probe {data.probeCount} · 达阈值 {data.passedCount}</text>}
    <g transform={`translate(${x},${y+54})`} className="communication-label" pointerEvents="none">
      <rect x={-88} y={-12} width={176} height={24} rx={5} fill="#132238"/>
      <text textAnchor="middle" dominantBaseline="central" fill={data.blocked?"#f9a5ac":"#bdd0e3"} fontSize={12}>{data.caption}</text>
    </g>
    {data.blocked&&<text x={x} y={y+5} textAnchor="middle" fill="#f17f86" fontSize={23}>⊘</text>}
  </>;
}
const nodeTypes={agent:AgentNode};
const edgeTypes={evidence:EvidenceEdge};
function ResponsiveViewport({bounds}:{bounds:Rect}) {
  const width=useStore(state=>state.width), height=useStore(state=>state.height);
  const {setViewport}=useReactFlow();
  useEffect(()=>{
    if(!width||!height)return;
    const frame=requestAnimationFrame(()=>void setViewport(getViewportForBounds(bounds,width,height,.25,1.1,.2)));
    return()=>cancelAnimationFrame(frame);
  },[bounds,width,height,setViewport]);
  return null;
}
export function AgentCanvas({graph,layoutGraph,selected,onSelect,probeLayer,messageLayer,preview,target,playing,search}: {
  graph:GraphView;layoutGraph:GraphView;selected:string;onSelect:(id:string)=>void;probeLayer:boolean;messageLayer:boolean;
  preview:string;target:string;playing:boolean;search:string;
}) {
  const foldedFour=layoutGraph.nodes.length===4&&["planner","data_agent","sender","receiver"].every(id=>layoutGraph.nodes.some(n=>n.id===id));
  const fixedTwo=layoutGraph.nodes.length===2&&["sender","receiver"].every(id=>layoutGraph.nodes.some(n=>n.id===id));
  const positions=useMemo(()=>{
    if(fixedTwo)return new Map([["sender",{x:45,y:50}],["receiver",{x:315,y:50}]]);
    // 固定四节点场景折叠为两行；只放置实际出现的节点，不改变消息关系。
    if(foldedFour)return new Map([
      ["planner",{x:45,y:50}],["data_agent",{x:315,y:50}],
      ["sender",{x:315,y:240}],["receiver",{x:45,y:240}],
    ]);
    const layout=new dagre.graphlib.Graph().setDefaultEdgeLabel(()=>({}));
    layout.setGraph({rankdir:layoutGraph.nodes.length>3?"TB":"LR",nodesep:70,ranksep:90,marginx:45,marginy:45});
    layoutGraph.nodes.forEach(node=>layout.setNode(node.id,{width:162,height:64}));
    layoutGraph.communication_edges.forEach(edge=>layout.setEdge(edge.source,edge.target));
    dagre.layout(layout);
    return new Map(layoutGraph.nodes.map(node=>[node.id,{x:layout.node(node.id).x-81,y:layout.node(node.id).y-32}]));
  },[layoutGraph,foldedFour,fixedTwo]);
  const bounds=useMemo(()=>{
    const points=[...positions.values()];
    if(!points.length)return {x:0,y:0,width:400,height:260};
    const x=Math.min(...points.map(p=>p.x))-18,y=Math.min(...points.map(p=>p.y))-70;
    return {x,y,width:Math.max(...points.map(p=>p.x))+180-x,height:Math.max(...points.map(p=>p.y))+134-y};
  },[positions]);
  const nodes:Node<AgentData>[]=graph.nodes.map(agent=>({id:agent.id,type:"agent",position:positions.get(agent.id)??{x:0,y:0},
    data:{agent,selectedAgent:selected===agent.id,preview:target===agent.id?preview:"",foldedFour,
      applied:graph.interventions.filter(item=>item.target.id===agent.id&&item.execution_state==="applied").map(item=>item.kind)},
    style:{opacity:search&&!agent.label.toLowerCase().includes(search.toLowerCase())?.28:1}}));
  const edges:Edge<EvidenceData>[]=messageLayer?graph.communication_edges.map(edge=>{
    const probes=probeLayer?graph.probe_evidence.filter(p=>p.associated_edge_id===edge.id):[];
    const isTarget=target===edge.id;
    const blocked=edge.blocked_count>0||(isTarget&&preview==="message_block");
    const replaced=graph.interventions.filter(item=>item.kind==="message_replace"&&item.target.id===edge.id&&item.execution_state==="applied").length;
    const noMatch=graph.interventions.filter(item=>item.kind==="message_replace"&&item.target.id===edge.id&&item.execution_state==="not_run").length;
    const caption=isTarget&&preview==="message_block"?"阻断预览 / 未运行":isTarget&&preview==="message_replace"?"替换预览 / 未运行"
      :blocked?`阻断 ${edge.blocked_count} · 交付 ${edge.delivered_count}`:replaced?`替换 ${replaced} · 未匹配 ${noMatch}`:noMatch?"无匹配 · 未实际替换":`消息交付 ${edge.delivered_count}`;
    return {id:edge.id,type:"evidence",source:edge.source,target:edge.target,animated:playing&&!blocked&&edge.delivered_count>0,
      markerEnd:{type:MarkerType.ArrowClosed,color:blocked?"#f17f86":"#48c4d4"},
      data:{observed:probes.length>0,passed:probes.some(p=>probeThreshold(p)===true),blocked,caption,probeCount:probes.length,passedCount:probes.filter(p=>probeThreshold(p)===true).length},
      style:{stroke:blocked?"#f17f86":"#48c4d4",strokeWidth:selected===edge.id?3:1.8,
        strokeDasharray:blocked?"7 6":edge.delivered_count===0?"4 5":undefined}};
  }):[];
  return <div className="agent-canvas" role="region" aria-label="Agent 通信图谱">
    <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} minZoom={.25} maxZoom={2} style={{background:"#0a1423"}}
      onNodeClick={(_,node)=>onSelect(node.id)} onEdgeClick={(_,edge)=>onSelect(edge.id)}
      proOptions={{hideAttribution:false}} colorMode="dark" nodesDraggable={false}>
      <Background bgColor="#0a1423" color="#26384c" gap={28} size={1}/><Controls showInteractive={false}/>
      <ResponsiveViewport bounds={bounds}/>
    </ReactFlow>
    {!nodes.length&&<div className="canvas-empty"><span>◎</span><strong>尚无可绘制的通信事实</strong><p>只有实际运行事件能够生成节点和消息边。<br/>示意网络在独立的 DEMO 中查看。</p></div>}
    <div className="canvas-legend"><span>━ 实际通信</span><span className="violet">┄ Probe 观测</span><span className="amber">┄ 目标标签达阈值</span><span className="coral">⊘ 阻断</span><span>◇ 因果机制未验证</span></div>
  </div>;
}

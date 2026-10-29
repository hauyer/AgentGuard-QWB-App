import {useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {apiGet} from "../../services/api";
import {AgentCanvas} from "./AgentCanvas";
import {atSequence, parseExperimentView, type ComparisonView, type ExperimentView, METHOD_NAMES} from "./model";

function pairedPhase(view:ExperimentView,family:string,phase:number) {
  const events=view.events.filter(e=>e.data.case_family===family);
  const candidates=phase===0?events.slice(0,1):phase===1?events.filter(e=>["agent_started","message_sent","message_delivered","message_blocked","message_replaced"].includes(e.type)):events;
  const seq=candidates.at(-1)?.seq??0;
  return atSequence({...view,events},seq);
}

/** Pair membership comes from the server comparison, never from chronological Run guesses. */
export function PairedRunReplay({base,comparison}:{base:string;comparison?:ComparisonView}) {
  const [open,setOpen]=useState(false);
  const [choice,setChoice]=useState("");
  const [selectedFamily,setFamily]=useState("");
  const [phase,setPhase]=useState(2);
  const rows=comparison?.arms.filter(row=>row.arm_id!=="baseline"&&row.baseline_run_id&&row.treatment_run_id)??[];
  const row=rows.find(r=>r.arm_id===choice)??rows[0];
  const member=(run?:string)=>comparison?.selected_runs?.find(r=>r.run_id===run)?.workflow_id;
  const control=member(row?.baseline_run_id), treatment=member(row?.treatment_run_id);
  const left=useQuery({queryKey:["paired-replay",base,control],enabled:open&&Boolean(control),
    queryFn:async({signal})=>parseExperimentView(await apiGet(`${base}/runs/${encodeURIComponent(control!)}/visualization`,signal))});
  const right=useQuery({queryKey:["paired-replay",base,treatment],enabled:open&&Boolean(treatment),
    queryFn:async({signal})=>parseExperimentView(await apiGet(`${base}/runs/${encodeURIComponent(treatment!)}/visualization`,signal))});
  const leftFamilies=new Set(left.data?.events.map(e=>String(e.data.case_family??"")).filter(Boolean));
  const families=[...new Set(right.data?.events.map(e=>String(e.data.case_family??"")).filter(f=>f&&leftFamilies.has(f)))].sort();
  const family=families.includes(selectedFamily)?selectedFamily:families[0]??"";
  return <section className="stego-panel paired-replay"><header><h2>同批次配对回放</h2><button className="quiet-button" onClick={()=>setOpen(!open)}>{open?"收起同步比较":"同步比较两个配对 Run"}</button></header>{open&&<>
    <div className="paired-replay-controls"><label>实验臂 <select aria-label="配对回放实验臂" value={row?.arm_id??""} onChange={e=>setChoice(e.target.value)}>{rows.map(r=><option key={r.arm_id} value={r.arm_id}>{METHOD_NAMES[r.arm_id]??r.arm_id}</option>)}</select></label>
      <label>家族 <select aria-label="配对回放家族" value={family} onChange={e=>setFamily(e.target.value)}>{families.map(f=><option key={f} value={f}>{f}</option>)}</select></label>
      <label>同步阶段 <select aria-label="配对回放阶段" value={phase} onChange={e=>setPhase(Number(e.target.value))}><option value={0}>开始执行</option><option value={1}>消息发送与交付</option><option value={2}>译码与任务结束</option></select></label>
      <span>按相同家族与阶段同步，不按不同 Run 的事件编号强行对齐。</span></div>
    {(left.error||right.error)&&<p className="replay-empty" role="alert">无法读取配对事件：{(left.error??right.error)?.message}</p>}
    {!row&&<p className="replay-empty">选择冻结批次后，等待至少一组经核验的 baseline 与干预 Run。</p>}
    {row&&(left.isLoading||right.isLoading)&&<p className="replay-empty">正在核验两个 Run 的事件与来源…</p>}
    {left.data&&right.data&&family&&<div className="paired-replay-grid">{[left.data,right.data].map((view,i)=><article key={view.workflow_id}><h3>{i===0?"Baseline":METHOD_NAMES[row!.arm_id]} · {view.graph.run_id}</h3><AgentCanvas graph={pairedPhase(view,family,phase)} layoutGraph={left.data!.graph} selected="" onSelect={()=>{}} probeLayer messageLayer preview="" target="" playing={false} search=""/></article>)}</div>}
  </>}</section>;
}

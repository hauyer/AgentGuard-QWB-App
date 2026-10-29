import { useInspectorDialog } from "../hooks/use-inspector-dialog";
import "../features/observatory/remediation.css";
import { useSubmissionIntent } from "../hooks/use-submission-intent";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Activity, ArrowRight, BarChart3, Check, ChevronRight, FileCheck2, FlaskConical,
  Layers3, Network, Pause, Play, Search, Shield, ShieldBan, X, Download } from "lucide-react";
import ReactECharts from "echarts-for-react";
import { apiGet, apiPost } from "../services/api";
import { useProjects } from "../hooks/use-projects";
import { useProjectStudies } from "../hooks/use-research";
import { useWorkspaceChrome } from "../components/layout/workspace-context";
import { useAuthStore } from "../stores/auth-store";
import { ResearchWorkbenchPage } from "./ResearchWorkbenchPage";
import { AgentCanvas } from "../features/observatory/AgentCanvas";
import {GradedDecisionPanel, type SecurityProfileView} from "../features/observatory/GradedDecisionPanel";
import { PairedRunReplay } from "../features/observatory/PairedRunReplay";
import { createDemoView } from "../features/observatory/demo";
import { atSequence, eventSelection, probeThreshold, METRIC_NAMES, METHOD_NAMES, parseExperimentView, parseComparisonView, type ComparisonView, type ExperimentView } from "../features/observatory/model";

type Desk = "home" | "detection" | "intervention" | "analysis" | "research";
const TITLES = {home:"多 Agent 隐蔽通信检测与干预实验平台",detection:"通信检测台",
  intervention:"干预实验台",analysis:"结果分析台",research:"研究管理"};
const NOTES = {home:"在受控多智能体协作场景中，发现可疑通信，验证防御效果，并衡量正常任务损失。",
  detection:"重建实际消息交付，检视内部可解码性。候选信号与因果结论分开呈现。",
  intervention:"在固定协议下改变目标条件；预览、已应用与已验证是三种不同状态。",
  analysis:"以独立案例家族配对，比较秘密恢复、译码缺失与正常任务效用。",
  research:"冻结研究协议、关联实验运行，并沿证据链追溯每一次结果。"};

export function ObservatoryPage({desk="home"}:{desk?:Desk}) {
  const setChromeSource=useWorkspaceChrome()?.setSource;
  const [params,setParams]=useSearchParams();
  const isDemo=params.get("mode")==="demo";
  const projects=useProjects(200);
  const projectId=params.has("projectId")?Math.max(0,Number(params.get("projectId"))||0):projects.data?.items[0]?.project_id||0;
  const studies=useProjectStudies(projectId);
  const studyId=params.has("studyId")?(params.get("studyId")??""):studies.data?.items.find(item=>item.track==="live_steganography")?.study_id||studies.data?.items[0]?.study_id||"";
  const study=studies.data?.items.find(item=>item.study_id===studyId);
  const base=`/projects/${projectId}/studies/${encodeURIComponent(studyId)}`;
  const runs=useQuery({queryKey:["observatory-runs",projectId,studyId],queryFn:({signal})=>apiGet<{items:{workflow_id:string;run_id:string;status:string;arm_id?:string;batch_id?:string;replicate_id?:string;updated_at?:string}[]}>(`${base}/runs`,signal),
    enabled:!isDemo&&projectId>0&&Boolean(studyId),refetchInterval:query=>query.state.data?.items.some(item=>["planned","running","queued","accepted"].includes(item.status))?5000:false});
  const workflowId=params.has("workflowId")?(params.get("workflowId")??""):runs.data?.items.find(item=>item.status==="completed")?.workflow_id||runs.data?.items[0]?.workflow_id||"";
  const visualization=useQuery({queryKey:["observatory",projectId,studyId,workflowId],
    queryFn:async({signal})=>parseExperimentView(await apiGet(`${base}/runs/${encodeURIComponent(workflowId)}/visualization`,signal)),
    enabled:!isDemo&&projectId>0&&Boolean(studyId&&workflowId),retry:(count,error)=>count<2&&![401,403,404,422].includes((error as {status?:number}).status??0)});
  useQuery({queryKey:["observatory-cursor",projectId,studyId,workflowId,visualization.data?.last_seq],
    queryFn:async({signal})=>{
      const page=await apiGet<{schema_version:string;last_seq:number;status:string}>(`${base}/runs/${encodeURIComponent(workflowId)}/timeline?after_seq=${visualization.data?.last_seq??0}&limit=200`,signal);
      if(page.schema_version!=="stego.timeline/1"||!Number.isSafeInteger(page.last_seq))throw new Error("时间线合同不兼容。");
      if(page.last_seq!==(visualization.data?.last_seq??0)||page.status!==visualization.data?.status)await visualization.refetch();
      return page;
    },enabled:!isDemo&&["planned","running","queued","accepted"].includes(visualization.data?.status??""),refetchInterval:3000});
  const batches=useQuery({queryKey:["observatory-batches",projectId,studyId],
    queryFn:({signal})=>apiGet<{items:{batch_id:string;replicate_id?:string;items:{arm_id:string;workflow_id:string;run_id:string|null}[]}[]}>(`${base}/run-batches`,signal),
    enabled:!isDemo&&projectId>0&&Boolean(studyId)});
  const batchId=params.get("batchId")??"";
  useEffect(()=>{
    if(isDemo||!batchId||!batches.data)return;
    const batch=batches.data.items.find(item=>item.batch_id===batchId);
    if(!batch||batch.items.some(item=>item.workflow_id===workflowId))return;
    const member=batch.items.find(item=>item.arm_id==="baseline")??batch.items[0];
    if(member){const next=new URLSearchParams(params);next.set("workflowId",member.workflow_id);setParams(next,{replace:true});}
  },[isDemo,batchId,batches.data,workflowId,params,setParams]);
  const comparison=useQuery({queryKey:["observatory-comparison",projectId,studyId,batchId],
    queryFn:async({signal})=>parseComparisonView(await apiGet(batchId?`${base}/comparisons/batches/${encodeURIComponent(batchId)}`:`${base}/comparison`,signal)),
    enabled:!isDemo&&["analysis","detection","intervention"].includes(desk)&&(desk==="analysis"||Boolean(batchId))&&Boolean(studyId)&&visualization.isSuccess,
    staleTime:30000,
    refetchInterval:query=>query.state.data?.status==="incomplete"&&runs.data?.items.some(item=>["planned","running","queued","accepted"].includes(item.status))?30000:false});
  const demo=useMemo(createDemoView,[]);
  const view=isDemo?demo:visualization.data;
  const update=(fields:Record<string,string|null>)=>{
    const next=new URLSearchParams(params);
    Object.entries(fields).forEach(([key,value])=>value===null?next.delete(key):next.set(key,value));
    setParams(next);
  };
  useEffect(()=>{
    if(isDemo||!projectId||!studyId||!workflowId)return;
    if(params.has("projectId")&&params.has("studyId")&&params.has("workflowId"))return;
    const next=new URLSearchParams(params);next.set("projectId",String(projectId));next.set("studyId",studyId);next.set("workflowId",workflowId);
    setParams(next,{replace:true});
  },[isDemo,projectId,studyId,workflowId,params,setParams]);
  const query=params.toString()?`?${params}`:"";
  const actualMode=isDemo?"DEMO":view?.origin_mode==="LIVE_S"?"RECORDED · S":view?.origin_mode==="LIVE_M"?"RECORDED · M":projects.isLoading||studies.isLoading||runs.isLoading||visualization.isLoading?"读取中":workflowId?"UNAVAILABLE":"未选择运行";
  const error=isDemo?null:projects.error??studies.error??runs.error??visualization.error;
  useEffect(()=>{setChromeSource?.(actualMode);return()=>setChromeSource?.(null);},[setChromeSource,actualMode]);
  return <>
        <div className="desk-title"><div><p className="eyebrow">{desk==="home"?"MULTI-AGENT SECURITY OBSERVATORY":"EXPERIMENT WORKSPACE"}</p><h1>{TITLES[desk]}</h1><p>{NOTES[desk]}</p></div><button className={`quiet-button ${isDemo?"selected":""}`} onClick={()=>update({mode:isDemo?null:"demo"})}>{isDemo?"退出示意场景":"查看示意场景"}<ArrowRight size={14}/></button></div>
        {isDemo&&<div className="demo-notice" role="status"><ShieldBan size={15}/><strong>DEMO · 预置示意场景，非实测</strong><span>所有图谱与 Probe 仅用于演示交互；不会写入研究数据库。</span></div>}
        <fieldset className="experiment-context" disabled={isDemo}>
          <label>项目<select aria-label="实验项目" value={isDemo?0:projectId} onChange={event=>update({projectId:event.target.value,studyId:null,workflowId:null,batchId:null,compareWorkflowId:null})}><option value={0}>{isDemo?"示意场景":"选择已有项目"}</option>{projects.data?.items.map(item=><option key={item.project_id} value={item.project_id}>{item.name}</option>)}</select></label>
          <label>Study<select aria-label="研究记录" value={isDemo?"":studyId} onChange={event=>update({studyId:event.target.value,workflowId:null,batchId:null,compareWorkflowId:null})}><option value="">选择研究记录</option>{studies.data?.items.filter(item=>item.study_id).map(item=><option key={item.study_id} value={item.study_id!}>{item.title}</option>)}</select></label>
          <label>Run<select aria-label="实验运行" value={isDemo?"":workflowId} onChange={event=>update({workflowId:event.target.value})}><option value="">选择已有运行</option>{runs.data?.items.filter(item=>!batchId||batches.data?.items.find(b=>b.batch_id===batchId)?.items.some(member=>member.workflow_id===item.workflow_id)).map(item=><option key={item.workflow_id} value={item.workflow_id}>{item.arm_id?(METHOD_NAMES[item.arm_id]??item.arm_id)+" · ":""}{item.run_id??item.workflow_id} · {item.status}</option>)}</select></label>
          <div className="context-track"><span className={`status-dot ${view?.status==="completed"?"":view?.status==="failed"||view?.status==="blocked"?"is-failed":view?"is-pending":"is-unknown"}`}/><strong>{isDemo?"示意回放":view?.status??(runs.isLoading||visualization.isLoading?"正在读取":"尚未选择运行")}</strong><small>{isDemo?"非实测":study?.track==="live_steganography"?"S 轨道 · 真实通信":study?.track==="mechanism_testbed"?"M 轨道 · 机制采集":"没有实验数据"}</small></div>
        </fieldset>
        {!isDemo&&["analysis","detection","intervention"].includes(desk)&&<label className="comparison-scope">比较批次<select aria-label="比较批次" value={batchId} onChange={event=>{const batch=batches.data?.items.find(b=>b.batch_id===event.target.value);const member=batch?.items.find(item=>item.workflow_id===workflowId)??batch?.items.find(item=>item.arm_id==="baseline")??batch?.items[0];update({batchId:event.target.value||null,...(member?{workflowId:member.workflow_id}:{})});}}><option value="">选择冻结批次（多次实验不可混合）</option>{batches.data?.items.map(batch=><option key={batch.batch_id} value={batch.batch_id}>{batch.replicate_id??"历史批次"} · {batch.batch_id}</option>)}</select><small>按不可变批次成员选择 Run，失败尝试与缺失臂保留。</small>{batches.error&&<span role="alert">{batches.error.message}</span>}</label>}
        {error&&<div className="error-notice" role="alert">实验数据无法核验：{error.message}<button onClick={()=>{if(projects.error)void projects.refetch();else if(studies.error)void studies.refetch();else if(runs.error)void runs.refetch();else void visualization.refetch();}}>重新查询</button></div>}
        {visualization.isFetching&&!isDemo&&<p className="loading-note">正在读取并核验实验事件…</p>}
        {desk==="research"?<div className="research-desk"><section className="stego-panel"><header><FlaskConical size={16}/><h2>研究与实验运行</h2><span>{isDemo?"示意场景":runs.isSuccess?"项目归属已核验":"读取项目记录"}</span></header><div className="comparison-table"><table><thead><tr><th>Study</th><th>运行 ID</th><th>状态</th><th>证据操作</th></tr></thead><tbody>{(!isDemo?runs.data?.items:[])?.map(item=><tr key={item.workflow_id}><td>{study?.title??studyId}<small>{study?.track}</small></td><td><code>{item.run_id??item.workflow_id}</code></td><td><span className="source-badge">{item.status}</span></td><td><Link className="quiet-button" to={`/detection?projectId=${projectId}&studyId=${studyId}&workflowId=${item.workflow_id}`}>查看通信事件<ArrowRight size={12}/></Link></td></tr>)}</tbody></table>{!isDemo&&runs.isLoading&&<p className="table-empty" role="status">正在读取实验运行…</p>}{isDemo&&<p className="table-empty">示意场景不关联真实研究记录。</p>}{!isDemo&&!runs.isLoading&&!runs.error&&!runs.data?.items.length&&<p className="table-empty">尚无实验运行。展开研究配置，登记协议并提交冻结实验臂。</p>}</div></section>{!isDemo&&<details className="research-config"><summary>研究工作台 · 预注册与高级配置</summary>{projectId>0?<ResearchWorkbenchPage embedded/>:<p className="muted">请先选择项目，再登记研究配置。</p>}</details>}</div>
          :desk==="analysis"?<AnalysisDesk base={base} comparison={isDemo?undefined:comparison.data} view={view} isDemo={isDemo} error={comparison.error?.message} loading={comparison.isLoading} query={query}/>
          :<Workspace key={`${projectId}:${studyId}:${workflowId}:${isDemo}`} desk={desk} view={view}
             projectId={projectId} studyId={studyId} study={study?.study??null} isDemo={isDemo}
             onSubmitted={id=>update({workflowId:id})} query={query}/>}
        {!isDemo&&["detection","intervention"].includes(desk)&&<PairedRunReplay key={`${studyId}:${batchId}`} base={base} comparison={comparison.data}/>}
  </>;
}

function Workspace({desk,view,projectId,studyId,study,isDemo,onSubmitted,query}:{desk:Desk;view?:ExperimentView;projectId:number;studyId:string;study:Record<string,unknown>|null;isDemo:boolean;onSubmitted:(id:string)=>void;query:string}) {
  const [selected,setSelected]=useState("");const [probeLayer,setProbeLayer]=useState(true);const [messageLayer,setMessageLayer]=useState(true);
  const securityBase=`/projects/${projectId}/studies/${encodeURIComponent(studyId)}`;
  const [profileId,setProfileId]=useState("");
  const profiles=useQuery({queryKey:["gsei-profiles",securityBase],queryFn:({signal})=>apiGet<{items:SecurityProfileView[]}>(`${securityBase}/security-profile`,signal),enabled:!isDemo&&!!studyId&&!!view});
  const profile=profiles.data?.items.find(p=>p.artifact_id===profileId)?.profile;
  const [cursor,setCursor]=useState<number|null>(null);const [playing,setPlaying]=useState(false);const [rate,setRate]=useState(1);
  const [methodChoice,setMethod]=useState("");
  const observedArm=view?.events[0]?.arm_id??"";
  const method=methodChoice||(["agent_isolation","message_block","message_replace","leace","activation_patch"].includes(observedArm)?observedArm:"message_block");const [preview,setPreview]=useState(false);const [target,setTarget]=useState("");
  const [family,setFamily]=useState("");
  const [search,setSearch]=useState("");const [inspector,setInspector]=useState(false);
  const closeInspector=useCallback(()=>setInspector(false),[]);
  const dialog=useInspectorDialog(inspector,closeInspector);
  const queryClient=useQueryClient();
  const seq=cursor??view?.last_seq??0;
  const graph=useMemo(()=>view?atSequence(family?{...view,events:view.events.filter(e=>e.data.case_family===family)}:view,seq):null,[view,seq,family]);
  useEffect(()=>{
    if(!playing||!view?.events.length)return;
    const motion=window.matchMedia("(prefers-reduced-motion: reduce)");
    const timer=window.setInterval(()=>setCursor(previous=>{
      const next=(previous??0)+1;if(next>=view.last_seq){setPlaying(false);return view.last_seq;}return next;
    }),motion.matches?1000:1000/rate);
    return()=>window.clearInterval(timer);
  },[playing,rate,view]);
  const role=useAuthStore(state=>state.role);
  const maySubmit=role==="analyst"||role==="operator"||role==="admin";
  const arms=Array.isArray(study?.arms)?study.arms as {arm_id:string}[]:[];
  const username=useAuthStore(state=>state.username);
  const submission=useSubmissionIntent(`${username}:${projectId}:${studyId}:${method}`);
  const run=useMutation({mutationFn:()=>{
    submission.markUncertain();
    return apiPost<{workflow_id?:string;status:string;blockers?:string[]}>(`/projects/${projectId}/studies/${encodeURIComponent(studyId)}/runs`,{arm_id:method},{"Idempotency-Key":submission.intent.key});
  },onSuccess:response=>{if(response.workflow_id){submission.markAccepted();onSubmitted(response.workflow_id);void queryClient.invalidateQueries({queryKey:["observatory-runs",projectId,studyId]});}}});
  const lookup=useMutation({mutationFn:async()=>{
    const base=`/projects/${projectId}/studies/${encodeURIComponent(studyId)}`;
    const result=await apiGet<{registered:boolean;workflow_id:string;run_id:string|null;arm_id?:string;status:string}>(`${base}/submission-intents/${encodeURIComponent(submission.intent.key)}`);
    if(result.registered&&!result.run_id){
      const existing=await apiGet<{run_id?:string;run?:{run_id?:string}}>(`${base}/runs/${encodeURIComponent(result.workflow_id)}`);
      result.run_id=existing.run?.run_id??existing.run_id??null;
    }
    if(result.arm_id&&result.arm_id!==method)throw new Error("提交标识关联了不同实验臂，请保留原记录进行核对。");
    return result;
  },onSuccess:result=>{if(result.run_id){submission.markAccepted();onSubmitted(result.workflow_id);}}});
  const select=(id:string)=>{setSelected(id);setTarget(id);setInspector(true);};
  const selectedNode=graph?.nodes.find(node=>node.id===selected);
  const selectedEdge=graph?.communication_edges.find(edge=>edge.id===selected);
  const evidence=graph?.probe_evidence.filter(probe=>probe.agent_id===selected||probe.associated_edge_id===selected)??[];
  const selectedEvents=view?.events.filter(event=>event.seq<=seq&&(event.actor_id===selected||selectedEdge?.message_ids.includes(event.message_id??"")))??[];
  const registered=arms.some(arm=>arm.arm_id===method);
  const frozenTarget=useQuery({queryKey:["frozen-execution-target",projectId,studyId,method],
    queryFn:({signal})=>apiGet<{status:string;contract:Record<string,unknown>&{target_ref:string}}>(`/projects/${projectId}/studies/${encodeURIComponent(studyId)}/arms/${encodeURIComponent(method)}/execution-contract`,signal),
    enabled:!isDemo&&registered&&Boolean(studyId),retry:false});
  const actualTarget=target||(method.startsWith("message_")?graph?.communication_edges[0]?.id:graph?.nodes.find(node=>node.id===(method==="agent_isolation"?"sender":"receiver"))?.id)||"";
  const families=[...new Set(view?.events.map(e=>String(e.data.case_family??"")).filter(Boolean))];
  const timelineEvents=view?.events.filter(event=>!family||event.data.case_family===family)??[];
  const frozenSummary=isDemo?null:frozenTarget.data?.contract??null;
  const emptyGraph={schema_version:"stego.graph/1" as const,study_id:studyId,run_id:null,track:"mechanism_testbed",state:"unavailable",nodes:[],communication_edges:[],probe_evidence:[],interventions:[],evidence_status:"not_run",limitations:[]};
  const exportView=()=>{
    if(!view)return;const blob=new Blob([JSON.stringify({...view,export_note:isDemo?"DEMO_NON_MEASURED":"VERIFIED_PUBLIC_VIEW_ONLY"},null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=isDemo?"DEMO-non-measured-view.json":"public-experiment-view.json";a.click();URL.revokeObjectURL(url);
  };
  return <>
    {desk==="home"&&<div className="experiment-story"><div><span className="step-number">01</span><strong>重建通信事实</strong><small>以真实消息事件生成有向拓扑</small></div><ChevronRight/><div><span className="step-number">02</span><strong>检视表示证据</strong><small>Probe 只陈述线性可解码性</small></div><ChevronRight/><div><span className="step-number">03</span><strong>干预与验证</strong><small>比较配对行为与正常任务效用</small></div><Link className="primary-button" to={`/detection${query}`}>开始检测<ArrowRight size={14}/></Link><Link className="quiet-button" to={`/intervention-lab${query}`}>进入干预实验</Link><Link className="quiet-button" to={`/analysis${query}`}>查看结果</Link></div>}
    {!isDemo&&view&&["detection","intervention"].includes(desk)&&<details className="gsei-disclosure"><summary>节点保护、通道保障与四层干预决策</summary><GradedDecisionPanel key={`${view.workflow_id}:${selected}`} base={securityBase} view={view} selected={selected} profiles={profiles.data?.items??[]} profileId={profileId} onProfile={setProfileId} onSubmitted={onSubmitted}/></details>}
    <div className={`observatory-workspace ${desk==="intervention"?"with-methods":""}`}>
      {desk==="intervention"&&<section className="stego-panel method-panel"><header><Shield size={15}/><h2>干预条件</h2><span>04 层级方法</span></header><div className="method-list">{["agent_isolation","message_block","message_replace","leace","activation_patch"].map(id=><button key={id} className={method===id?"selected":""} onClick={()=>{setMethod(id);setPreview(false);setTarget("");}}><span className="method-radio"/>{METHOD_NAMES[id]}<small>{id.startsWith("message_")?"作用于实际消息信道":id==="agent_isolation"?"跳过目标策略调用":"作用于 Agent 内部表示"}</small></button>)}</div><div className="method-explainer"><strong>预览 ≠ 应用 ≠ 有效</strong><p>只有执行事件支持“已应用”，配对行为和负对照才支持效果解释。</p><p>Path Patching：UNSUPPORTED</p></div></section>}
      <section className="stego-panel graph-panel"><header><Network size={16}/><h2>{desk==="intervention"?"干预前后 · 稳定拓扑":"Agent 通信拓扑"}</h2><span className="graph-count">{graph?.nodes.length??0} AGENTS</span><button className="icon-button" aria-label="导出公开视图" onClick={exportView} disabled={!view}><Download size={14}/></button></header>
        <div className="graph-toolbar"><div className="segmented"><button className={messageLayer?"active":""} onClick={()=>setMessageLayer(!messageLayer)}>通信层</button><button className={probeLayer?"active":""} onClick={()=>setProbeLayer(!probeLayer)}>Probe 证据</button></div><label className="graph-search"><Search size={13}/><input aria-label="搜索 Agent" placeholder="查找 Agent" value={search} onChange={event=>setSearch(event.target.value)}/></label><button className="quiet-button inspector-toggle" onClick={()=>setInspector(true)}>检视器</button></div>
        <div className="graph-coordinate"><span>事件重放 / SEQ {seq.toString().padStart(2,"0")}</span><span className={preview?"amber":""}>{preview?"PREVIEW · 未运行":isDemo?"DEMO · 非实测":graph?.evidence_status==="verified"?"已核验事件":"无通信事件"}</span></div>
        <AgentCanvas graph={{...(graph??emptyGraph),nodes:(graph??emptyGraph).nodes.map(n=>({...n,protection_level:profile?.nodes.find(s=>s.agent_id===n.id)?.protection_level??null})),communication_edges:(graph??emptyGraph).communication_edges.map(e=>({...e,assurance_level:profile?.channels.find(q=>q.edge_id===e.id)?.assurance_level??null}))}} layoutGraph={view?.graph??emptyGraph} selected={selected} onSelect={select} probeLayer={probeLayer} messageLayer={messageLayer} preview={preview?method:""} target={actualTarget} playing={playing} search={search}/>
        {isDemo&&<div className="demo-watermark">DEMO / NON-MEASURED</div>}
        <div className="graph-bottom-note"><FileCheck2 size={13}/>{view?.unavailable_reason?"此运行没有已记录的通信事件，系统不会推断消息边。":"通信边来自发送与交付事实；紫色只表示 Probe 线性证据。"}</div>
      </section>
      {dialog.modal&&<button className="inspector-scrim" aria-label="收起检视器遮罩" onClick={closeInspector}/>}
      <aside ref={dialog.element} role={dialog.modal?"dialog":undefined} aria-modal={dialog.modal||undefined} aria-label="上下文检视器" className={`stego-panel context-inspector ${inspector?"drawer-open":""}`}><header><Layers3 size={15}/><h2>{desk==="intervention"?"方法与执行检视":"上下文检视器"}</h2><button className="icon-button inspector-close" aria-label="关闭检视器" onClick={()=>setInspector(false)}><X size={17}/></button></header><div className="inspector-body">
        {desk==="intervention"?<><span className="inspector-symbol"><Shield size={23}/></span><h3>{METHOD_NAMES[method]}</h3><p className="muted">{method==="leace"?"在 train 家族拟合线性擦除器，再对独立 test 家族续算生成。不会自动把风险变绿。":method==="activation_patch"?"在同一模型调用内部替换指定层/Token；对齐 donor 与 recipient 后续算真实生成。":"对冻结协议中的 Agent 或消息执行受控消融，并保留正常任务结果。"}</p>
          <label className="inspector-field">预览目标<select value={actualTarget} onChange={event=>setTarget(event.target.value)}>{(method.startsWith("message_")?graph?.communication_edges:graph?.nodes)?.map(item=><option key={item.id} value={item.id}>{item.id}</option>)}</select></label><div className="preview-warning"><strong>{preview?"PREVIEW · 未运行":"实际执行使用服务端冻结目标"}</strong><p>改变此处只影响视觉预览；提交不会透传任意目标、模型路径或参数。</p></div><details className="frozen-target-summary"><summary>当前 Run 的实际执行证据</summary><p>实际实验臂：{observedArm||"暂无事件"}</p>{graph?.interventions.filter(item=>item.execution_state!=="planned").slice(-6).map(item=><p key={item.id}>{METHOD_NAMES[item.kind]??item.kind} · {item.execution_state} · {item.target.id}</p>)}{["PROBE_BEFORE_ACCURACY","PROBE_AFTER_ACCURACY","PROBE_RETRAINED_AFTER_ACCURACY"].map(name=><p key={name}>{name}：{view?.metrics[name]?.value?.toFixed(3)??"未测量"}（完整 Run/test，n={view?.metrics[name]?.denominator??"—"}）</p>)}<p>这些是聚合准确率，不能替代单案例 Probe 分数或行为效果。</p></details><button className="quiet-button wide" disabled={!graph?.nodes.length} onClick={()=>setPreview(!preview)}>{preview?"撤销预览":"预览效果"}</button>
          <p className="frozen-target-label">本次提交目标：<strong>{frozenSummary?.target_ref??(isDemo?"DEMO 无真实目标":frozenTarget.isLoading?"正在核对…":"尚无已核验目标")}</strong></p>{frozenTarget.error&&<p className="error-text" role="alert">无法核对实际目标：{frozenTarget.error.message}</p>}<details className="frozen-target-summary"><summary>提交前核对服务端冻结配置</summary><pre>{JSON.stringify(frozenSummary,null,2)}</pre><p>图中选择仅用于预览，不会替换下列协议、版本和采集坐标。</p></details>
          <button className="primary-button wide" disabled={isDemo||!maySubmit||!registered||run.isPending||!studyId||frozenTarget.data?.status!=="verified_frozen_contract"} onClick={()=>run.mutate()}>{run.isPending?"正在提交…":"提交冻结实验臂"}<ArrowRight size={14}/></button><div className="intent-actions"><button className="quiet-button" disabled={isDemo||run.isPending||submission.intent.state==="uncertain"} onClick={()=>{submission.newReplicate();run.reset();}}>新建单臂重复</button><button className="quiet-button" disabled={isDemo||lookup.isPending} onClick={()=>lookup.mutate()}>查询已有任务</button></div><p className="hash-text">提交标识：{submission.intent.replicate_id}</p>{lookup.error&&<p className="error-text" role="alert">{lookup.error.message}</p>}{lookup.data&&!lookup.data.run_id&&<p className="amber">{lookup.data.registered?"工作流已登记，远端任务尚未确认。":"尚未查到本次提交。"}请保留原提交意图进行查询或重试。</p>}<p className="small muted">{isDemo?"DEMO 禁止写入真实研究。":!registered?"当前 Study 未注册此实验臂：NOT_RUN。":"需项目角色、CSRF 和服务端协议授权。重试使用同一提交意图；正式重复比较请在研究管理创建冻结批次。"}</p>{run.error&&<p className="error-text" role="alert">{run.error.message}</p>}{run.data&&!run.data.workflow_id&&<p className="amber">{run.data.status} · {run.data.blockers?.join(" / ")}</p>}</>
        :<><span className="inspector-symbol"><Network size={24}/></span><h3>{selectedNode?.label??selectedEdge?.id??"选择节点或通信边"}</h3><p className="muted">{selectedEdge?"实际消息信道 · 只读证据":selectedNode?"Agent 运行事实":"点击图谱，查看角色、交付事件与证据来源。"}</p><dl className="inspector-kv"><div><dt>来源</dt><dd>{isDemo?"DEMO / 非实测":view?.origin_mode??"UNAVAILABLE"}</dd></div><div><dt>已交付消息</dt><dd>{selectedEdge?.delivered_count??"—"}</dd></div><div><dt>已阻断消息</dt><dd>{selectedEdge?.blocked_count??"—"}</dd></div><div><dt>状态</dt><dd>{selectedNode?.status??graph?.evidence_status??"not_run"}</dd></div></dl><h4>Probe Inspector</h4>{evidence.length?evidence.map((probe,index)=><details className="probe-item" key={probe.id} open={index===evidence.length-1}><summary>分数 {probe.value?.toFixed(4)??"未测量"} · {probeThreshold(probe)===true?"目标标签达阈值":"Probe 观测"}</summary><span>未校准分数 · 非隐蔽通信概率</span><dl className="inspector-kv"><div><dt>标签</dt><dd>{probe.label_semantics}</dd></div><div><dt>位置</dt><dd>L{probe.target_layer} / {probe.token_policy}</dd></div><div><dt>评价切分</dt><dd>{probe.evaluation_split}</dd></div><div><dt>冻结阈值</dt><dd>{probe.threshold?.toFixed(3)??"—"}</dd></div><div><dt>是否达阈值</dt><dd>{probeThreshold(probe)===null?"未知":probeThreshold(probe)?"是 · 目标标签候选读出":"否 · 仅观测"}</dd></div><div><dt>阈值来源</dt><dd>{probe.threshold_source??"未记录"}</dd></div><div><dt>Probe 版本</dt><dd>{probe.probe_model_version??"历史事件未提供"}</dd></div><div><dt>证据等级</dt><dd>{probe.claim_level}</dd></div><div><dt>概率校准</dt><dd>{probe.probability_calibrated?"是":"否"}</dd></div></dl><p className="hash-text">{probe.evidence_refs.join("\n")}</p></details>):<p className="muted small">没有与所选对象对应的 Probe 观测，不生成占位分数。</p>}<h4>来源事件</h4><div className="source-events">{selectedEvents.slice(-5).map(event=><button key={event.event_id} onClick={()=>setCursor(event.seq)}><span>#{event.seq} {event.type}</span><ChevronRight size={12}/></button>)}{!selectedEvents.length&&<p className="muted small">尚未选择事实事件。</p>}</div></>}
        {view?.artifacts.map(artifact=><details className="artifact-proof" key={artifact.artifact_id}><summary><FileCheck2 size={13}/>查看来源工件</summary><p>{artifact.artifact_id}</p><code>{artifact.sha256}</code><button onClick={()=>void navigator.clipboard?.writeText(artifact.sha256)}>复制 SHA-256</button></details>)}
      </div></aside>
    </div>
    <section className="stego-panel timeline-panel"><header><Activity size={15}/><h2>实验事件时间轴</h2><span>{view?.events.length??0} 条{isDemo?"示意":"实际"}事件</span><div className="playback"><button className="icon-button" aria-label={playing?"暂停事件回放":"播放事件回放"} disabled={!view?.events.length} onClick={()=>{if(seq===view?.last_seq)setCursor(0);setPlaying(!playing);}}>{playing?<Pause size={14}/>:<Play size={14}/>}</button><button className="quiet-button" onClick={()=>setRate(rate===2?.5:rate===.5?1:2)}>{rate}×</button><span>SEQ {seq}/{view?.last_seq??0}</span></div></header><div className="timeline-content"><input aria-label="事件时间游标" type="range" min={0} max={view?.last_seq??0} value={seq} onChange={event=>{setPlaying(false);setCursor(Number(event.target.value));}} disabled={!view?.events.length}/><div className="timeline-filters"><label>案例家族<select aria-label="回放案例家族" value={family} onChange={event=>setFamily(event.target.value)}><option value="">全部家族</option>{families.map(id=><option key={id} value={id}>{id}</option>)}</select></label><span>Run：{view?.graph.run_id??"未选择"} · Arm：{view?.events[0]?.arm_id??"—"}</span></div><div className="event-strip">{timelineEvents.map(event=><button key={event.event_id} className={event.seq===seq?"current":""} onClick={()=>{setPlaying(false);setCursor(event.seq);const id=eventSelection(event);if(id){setSelected(id);setInspector(true);}}}><span>{String(event.seq).padStart(2,"0")} · {event.at_utc.slice(11,19)} UTC</span><strong>{event.type.replaceAll("_"," ")}</strong><small>{event.actor_id??`${event.source_agent_id??""} → ${event.target_agent_id??""}`}</small></button>)}{!view?.events.length&&<p className="timeline-empty">尚无消息、干预或译码事件。回放不会重新执行模型。</p>}</div></div></section>
  </>;
}

function AnalysisDesk({base,comparison,view,isDemo,error,loading,query}:{base:string;comparison?:ComparisonView;view?:ExperimentView;isDemo:boolean;error?:string;loading:boolean;query:string}) {
  const exportBatch=useMutation({mutationFn:async()=>{
    if(isDemo||!comparison?.batch_id||!comparison.selected_runs)throw new Error("请先选择冻结批次。");
    const members=[];
    for(const member of comparison.selected_runs){
      const result=await apiGet(`${base}/runs/${encodeURIComponent(member.workflow_id)}`);
      members.push({selection:member,public_result:result});
    }
    const payload={schema_version:"stego.public-batch-export/1",exported_at_utc:new Date().toISOString(),
      evidence_boundary:"Verified public results and immutable batch membership; restricted activations and raw generations are excluded.",comparison,members};
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:"application/json"}));
    const a=document.createElement("a");a.href=url;a.download=`${comparison.batch_id}-public-results.json`;a.click();URL.revokeObjectURL(url);
  }});
  const rows=comparison?.arms??[];
  const adjusted=Object.values(comparison?.adjusted_pvalues??{});
  const collaborative=rows.some(row=>row.metrics?.UTILITY_COLLABORATIVE);
  const utilityMetric=collaborative?"UTILITY_COLLABORATIVE":"NORMAL_UTILITY";
  const metrics=["SRR_ITT","BER",utilityMetric];
  const measured=rows.filter(row=>row.status==="paired_observed"&&row.metrics?.[utilityMetric]?.value!=null&&row.effects?.SRR_ITT);
  const groups=new Map<string,{names:string[];value:number[]}>();
  measured.forEach(row=>{const value=[row.metrics![utilityMetric].value!,-row.effects!.SRR_ITT!.mean_treatment_minus_control];
    const key=value.join(":");const group=groups.get(key)??{names:[],value};group.names.push(METHOD_NAMES[row.arm_id]??row.arm_id);groups.set(key,group);});
  const option={backgroundColor:"transparent",tooltip:{trigger:"item"},grid:{left:65,right:25,bottom:55,top:25},
    xAxis:{type:"value",name:collaborative?"同路径协作任务效用":"独立任务读出（历史）",nameLocation:"middle",nameGap:30,min:0,max:1,axisLabel:{color:"#90a5bb"},splitLine:{lineStyle:{color:"#243448"}}},
    yAxis:{type:"value",name:"秘密恢复下降",min:-1,max:1,axisLabel:{color:"#90a5bb"},splitLine:{lineStyle:{color:"#243448"}}},
    series:[{type:"scatter",symbolSize:12,label:{show:true,formatter:"{b}",position:"left",align:"right",width:160,overflow:"break",color:"#cfdeef"},itemStyle:{color:"#5acfad"},
      labelLayout:{hideOverlap:true},data:[...groups.values()].map(group=>({label:{position:group.value[0]<.2?"right":"left",align:group.value[0]<.2?"left":"right"},name:group.names.length>1?`${group.names.length} 个实验臂 · 相同观测坐标`:group.names[0],value:group.value}))}]};
  return <div className="analysis-desk"><div className="analysis-export"><button className="quiet-button" disabled={isDemo||!comparison?.batch_id||exportBatch.isPending} onClick={()=>exportBatch.mutate()}><Download size={14}/>{exportBatch.isPending?"正在核验并汇集来源…":"导出当前批次与来源"}</button>{exportBatch.error&&<p role="alert" className="error-text">{exportBatch.error.message}</p>}</div><div className="metric-strip">{metrics.map(metric=>{const datum=view?.metrics[metric];return <article key={metric}><small>{METRIC_NAMES[metric]??metric}</small><strong>{datum?.value!=null?datum.value.toFixed(3):"—"}</strong><span>{datum?`分母 ${datum.denominator}`:isDemo?"DEMO 无实测数值":"尚无经核验的指标"}</span></article>})}<article><small>研究状态</small><strong className="metric-status">{isDemo?"DEMO":comparison?.research_validity==="baseline_gate_passed"?"基线门槛通过":comparison?.research_validity?"有效性未建立":comparison?.status??"INCOMPLETE"}</strong><span>运行完成、研究有效性与因果验证分开记录</span></article></div>
    <div className="analysis-grid"><section className="stego-panel"><header><BarChart3 size={16}/><h2>安全—效用比较</h2><span>独立 test 家族</span></header>{measured.length?<ReactECharts option={option} style={{height:350}}/>:<div className="chart-empty"><BarChart3 size={32}/><strong>{loading?"正在读取配对结果…":isDemo?"示意场景不生成效果数字":"尚无足够的配对行为结果"}</strong><p>只有核验后的真实实验臂才会生成数据点。</p></div>}</section><section className="stego-panel"><header><FileCheck2 size={16}/><h2>结论与证据边界</h2></header><div className="conclusion-body"><span className="evidence-label"><Check size={14}/>来源等级独立于运行完成状态</span><h3>{loading?"正在核验结果…":comparison?.status==="observed"?"已获得受控实验观察":"结果尚不完整"}</h3><p>{comparison?.baseline_srr?`基线恢复 ${comparison.baseline_srr.successes}/${comparison.baseline_srr.planned}，Wilson 95% 区间 [${comparison.baseline_srr.wilson_95_ci.map(v=>v.toFixed(3)).join(", ")}]。`:""}</p><p>受控词表通信不证明自发隐写；Probe 只说明目标标签的线性可解码性。内部干预需继续生成并与负对照比较。</p>{adjusted.length>0&&<p className="amber">多重比较校正（{comparison?.multiplicity_method??"未记录"}）后达到 0.05 的比较：{adjusted.filter(p=>p.reject_at_0_05).length}/{adjusted.length}。未达到阈值不等于证明无效或等效。</p>}{(comparison?.limitations??view?.limitations??[]).map(text=><p key={text}>{text}</p>)}{comparison?.research_limitations?.map(text=><p className="amber" key={text}>{text}</p>)}{comparison?.blockers.map(text=><p className="amber" key={text}>{text}</p>)}{error&&<p className="error-text">{error}</p>}<Link className="quiet-button" to={`/research${query}`}>查看研究与原始关联<ArrowRight size={13}/></Link></div></section></div>
    <details className="stego-panel metric-diagnostics"><summary>执行、载体与辅助任务指标</summary><div className="comparison-table"><table><thead><tr><th>实验臂</th>{["INVERTED_READOUT_SRR_ITT","RECEIVER_INPUT_NOVELTY_RATE","CARRIER_VALID_RATE","SRR_EXECUTED","UTILITY_INDEPENDENT","UTILITY_COLLABORATIVE","EXECUTION_SUCCESS_RATE","CARRIER_DELIVERY_RATE","SRR_NO_CARRIER","SRR_VALID_CARRIER"].map(m=><th key={m}>{METRIC_NAMES[m]}</th>)}</tr></thead><tbody>{rows.map(row=><tr key={row.arm_id}><td>{METHOD_NAMES[row.arm_id]??row.arm_id}</td>{["INVERTED_READOUT_SRR_ITT","RECEIVER_INPUT_NOVELTY_RATE","CARRIER_VALID_RATE","SRR_EXECUTED","UTILITY_INDEPENDENT","UTILITY_COLLABORATIVE","EXECUTION_SUCCESS_RATE","CARRIER_DELIVERY_RATE","SRR_NO_CARRIER","SRR_VALID_CARRIER"].map(m=><td key={m}>{row.metrics?.[m]?.value?.toFixed(3)??"未测量"}<small>n={row.metrics?.[m]?.denominator??"—"}</small></td>)}</tr>)}</tbody></table></div></details>
    <section className="stego-panel"><header><Activity size={16}/><h2>线性读出诊断</h2><span>secret_bit · 位置见原始 Probe 证据 · test</span></header><div className="comparison-table"><table><thead><tr><th>实验臂</th><th>原 Probe / 干预前</th><th>原 Probe / 干预后</th><th>擦除后重训 Probe / test</th></tr></thead><tbody>{rows.map(row=><tr key={row.arm_id}><td>{METHOD_NAMES[row.arm_id]??row.arm_id}</td>{["PROBE_BEFORE_ACCURACY","PROBE_AFTER_ACCURACY","PROBE_RETRAINED_AFTER_ACCURACY"].map(name=><td key={name}>{row.metrics?.[name]?.value?.toFixed(3)??"—"}<small>n={row.metrics?.[name]?.denominator??"—"}</small></td>)}</tr>)}</tbody></table><p className="table-empty">仅 train 拟合擦除器与 Probe；validation 选择阈值，独立 test 评价。重训 Probe 仅在 LEACE 臂定义。读出下降不代表行为防御有效。历史 NORMAL_UTILITY 为独立读出；v2 单独报告同路径 UTILITY_COLLABORATIVE。</p></div></section>
    <section className="stego-panel"><header><FlaskConical size={16}/><h2>实验臂与配对结果</h2><span>缺失不填零</span></header><div className="comparison-table"><table><thead><tr><th>实验臂</th><th>状态</th>{metrics.map(metric=><th key={metric}>{METRIC_NAMES[metric]??metric}</th>)}<th>效应 / 95% CI</th><th>校正 p 值</th><th>样本 / 缺失</th><th>Run 关联</th></tr></thead><tbody>{rows.map(row=><tr key={row.arm_id}><td>{METHOD_NAMES[row.arm_id]??row.arm_id}</td><td><span className="source-badge">{row.status}</span></td>{metrics.map(metric=><td key={metric}>{row.metrics?.[metric]?.value?.toFixed(3)??"—"}<small>n={row.metrics?.[metric]?.denominator??"—"}</small></td>)}<td>{row.effects?.SRR_ITT?`${row.effects.SRR_ITT.mean_treatment_minus_control.toFixed(3)} [${row.effects.SRR_ITT.cluster_bootstrap_95_ci.map(v=>v.toFixed(3)).join(", ")}]`:"INSUFFICIENT_PAIRS"}</td><td>{comparison?.adjusted_pvalues?.[row.arm_id]?.adjusted_p_value.toFixed(4)??"—"}<small>{comparison?.adjusted_pvalues?.[row.arm_id]?(comparison.adjusted_pvalues[row.arm_id].reject_at_0_05?"校正后达到 0.05":"校正后未达 0.05"):row.arm_id==="baseline"?"基线参考":"未提供校正结果"}</small></td><td>{row.sample_count??"—"} / {row.missing_count??"—"}</td><td><code>{row.treatment_run_id??row.blockers.join(" / ")}</code></td></tr>)}</tbody></table>{!rows.length&&<p className="table-empty">没有可比较的实验臂。系统不会预设“最优防御”或展示示例柱状图。</p>}</div></section>
  </div>;
}

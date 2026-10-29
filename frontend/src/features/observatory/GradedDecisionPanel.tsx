import {useState} from "react";
import {useMutation, useQueryClient} from "@tanstack/react-query";
import {apiPost} from "../../services/api";
import {useAuthStore} from "../../stores/auth-store";
import {METHOD_NAMES, type ExperimentView} from "./model";
import "./graded-security.css";

export interface SecurityProfileView {artifact_id:string;profile:{profile_id:string;policy_version:string;source_ref:string;nodes:{agent_id:string;protection_level:number|null}[];channels:{edge_id:string;assurance_level:number|null}[]}}
interface Candidate {level:string;method_id:string;arm_id:string|null;feasible:boolean;reasons:string[];objective:number|null;effect_evidence:unknown;execution_contract:unknown}
interface Decision {artifact_id:string;payload:{risk:{lower:number;upper:number;risk_score:number|null;status:string;explanation:unknown};candidates:Candidate[];decision_status:string;recommended_arm_id?:string|null}}
const LAYERS={L1:"组件级 · Neuron / Head / MLP",L2:"表示级 · Activation / Subspace",L3:"行为级 · 输出规则 / Steering",L4:"系统级 · Agent / 消息"};
const REASONS:Record<string,string>={UNSUPPORTED:"尚无经过验证的执行协议",FROZEN_ARM_NOT_REGISTERED:"当前研究未注册此实验臂",CAPABILITY_UNAVAILABLE:"当前执行能力不可用",FROZEN_TARGET_MISMATCH:"冻结目标与事件对象不匹配",FROZEN_CONTRACT_UNAVAILABLE:"尚未核验冻结合同",EXECUTION_AUTHORIZATION_REQUIRED:"当前角色缺少执行权限",MANDATORY_POLICY_DENIED:"安全策略禁止此动作",INSUFFICIENT_EFFECT_EVIDENCE:"效果证据尚不足以支持最优推荐",COST_AND_DISRUPTION_POLICY_NOT_REGISTERED:"尚未登记执行成本与波及范围政策"};
const STATUS:Record<string,string>={NEEDS_REVIEW:"待审核",CANDIDATES_ONLY:"候选建议，需人工核对",OPTIMIZED:"已按登记政策计算代价排序"};

export function GradedDecisionPanel({base,view,selected,profiles,profileId,onProfile,onSubmitted}:{base:string;view:ExperimentView;selected:string;profiles:SecurityProfileView[];profileId:string;onProfile:(id:string)=>void;onSubmitted:(id:string)=>void}){
 const role=useAuthStore(s=>s.role);const allowed=role==="operator"||role==="admin";const qc=useQueryClient();
 const [source,setSource]=useState("");const [levels,setLevels]=useState<Record<string,string>>({});
 const [harm,setHarm]=useState("");const [business,setBusiness]=useState("");const [violation,setViolation]=useState("");const [eventId,setEventId]=useState("");
 const [layer,setLayer]=useState("L2");const [decision,setDecision]=useState<Decision|null>(null);
 const [pairedBatch,setPairedBatch]=useState(false);
 const edge=view.graph.communication_edges.find(e=>e.id===selected);const node=view.graph.nodes.find(n=>n.id===selected);
 const events=view.events.filter(e=>e.evidence_refs.length>0&&(edge?edge.source_event_ids.includes(e.event_id)||edge.message_ids.includes(e.message_id??""):node?[e.actor_id,e.source_agent_id,e.target_agent_id].includes(node.id):false));
 const event=events.find(e=>e.event_id===eventId)??events[0];
 const save=useMutation({mutationFn:()=>apiPost<{artifact_id:string}>(`${base}/security-profile`,{profile_id:`profile-${crypto.randomUUID()}`,study_id:view.graph.study_id,workflow_id:view.workflow_id,policy_version:"gsei-policy-v1",source_ref:source,
  nodes:view.graph.nodes.map(n=>({agent_id:n.id,protection_level:levels[n.id]?Number(levels[n.id]):null})),channels:view.graph.communication_edges.map(e=>({edge_id:e.id,assurance_level:levels[e.id]?Number(levels[e.id]):null}))}),
  onSuccess:r=>{onProfile(r.artifact_id);void qc.invalidateQueries({queryKey:["gsei-profiles",base]});setDecision(null);}});
 const preview=useMutation({mutationFn:async()=>{
  if(!event||!profileId||!selected)throw new Error("请选择已配置安全策略、真实对象与来源事件。");
  const value=await apiPost<{artifact_id:string}>(`${base}/value-events?workflow_id=${encodeURIComponent(view.workflow_id)}&profile_artifact_id=${profileId}`,{event_id:event.event_id,study_id:event.study_id,run_id:event.run_id,target_type:edge?"edge":"node",target_ids:[selected],harm_level:harm?Number(harm):null,business_value:business?Number(business):null,policy_violation:violation===""?null:violation==="true",evidence_refs:event.evidence_refs,classification_source:source});
  const batchId=new URLSearchParams(window.location.search).get("batchId");
  return apiPost<Decision>(`${base}/intervention-decisions/preview`,{workflow_id:view.workflow_id,profile_artifact_id:profileId,event_artifact_id:value.artifact_id,...(batchId?{batch_id:batchId}:{})});
 },onSuccess:setDecision});
 const execute=useMutation({mutationFn:(arm:string)=>apiPost<{workflow_id:string}>(`${base}/intervention-decisions/${decision?.artifact_id}/execute`,{arm_id:arm,paired_batch:pairedBatch}),onSuccess:r=>onSubmitted(r.workflow_id)});
 const levelSelect=(id:string,prefix:string)=><select aria-label={`${prefix} ${id}`} value={levels[id]??""} onChange={e=>setLevels({...levels,[id]:e.target.value})}><option value="">未配置</option>{[1,2,3,4,5].map(n=><option key={n} value={n}>{prefix}{n}</option>)}</select>;
 return <section className="stego-panel gsei-panel"><header><h2>四层分级干预决策</h2><span>政策优先级评分 · 非有害概率</span></header><div className="gsei-body">
 <label>安全配置<select aria-label="安全等级配置" value={profileId} onChange={e=>{onProfile(e.target.value);setDecision(null);}}><option value="">未配置 · 等级未知</option>{profiles.map(p=><option key={p.artifact_id} value={p.artifact_id}>{p.profile.profile_id} · {p.profile.policy_version}</option>)}</select></label>
 <details><summary>登记经审核的等级配置</summary><p>等级来源：批准的安全配置或研究标注。保护需求 S 与通道保障 Q 分开登记。</p><div className="gsei-levels">{view.graph.nodes.map(n=><label key={n.id}>{n.label}{levelSelect(n.id,"S")}</label>)}{view.graph.communication_edges.map(e=><label key={e.id}>{e.id}{levelSelect(e.id,"Q")}</label>)}</div><button className="quiet-button" disabled={!allowed||!source.trim()||save.isPending} onClick={()=>save.mutate()}>保存不可变安全配置</button></details>
 <label>配置 / 事件分类依据<input aria-label="安全分类依据" placeholder="经审核的策略或研究标注引用" value={source} onChange={e=>setSource(e.target.value)}/></label>
 <p>当前对象：{selected||"请点击真实节点或通信边"}</p><label>来源事件<select aria-label="安全事件来源" value={event?.event_id??""} onChange={e=>{setEventId(e.target.value);setDecision(null);}}>{events.map(e=><option key={e.event_id} value={e.event_id}>#{e.seq} {e.type}</option>)}</select></label>
 <div className="gsei-levels"><label>安全危害 H<select aria-label="危害等级" value={harm} onChange={e=>{setHarm(e.target.value);setDecision(null);}}><option value="">未知</option>{[0,1,2,3,4,5].map(n=><option key={n}>{n}</option>)}</select></label><label>业务价值 B<select aria-label="业务价值" value={business} onChange={e=>{setBusiness(e.target.value);setDecision(null);}}><option value="">未知</option>{[1,2,3,4,5].map(n=><option key={n}>{n}</option>)}</select></label><label>策略违规<select aria-label="策略违规" value={violation} onChange={e=>{setViolation(e.target.value);setDecision(null);}}><option value="">未知</option><option value="true">已确认违规</option><option value="false">未违规</option></select></label></div>
 <button className="primary-button" disabled={!allowed||!profileId||!event||!source.trim()||preview.isPending} onClick={()=>preview.mutate()}>{preview.isPending?"正在核验…":"登记事件并预览决策"}</button>
 <div className="segmented">{Object.entries(LAYERS).map(([id,name])=><button key={id} className={layer===id?"active":""} onClick={()=>setLayer(id)}>{id} {name}</button>)}</div>
 <label className="gsei-paired-choice"><input type="checkbox" checked={pairedBatch} onChange={e=>setPairedBatch(e.target.checked)}/>新建完整注册批次（包括基线和所有注册臂），用于同批次比较</label>
 {!decision&&<p>选择真实事件后生成可行候选。L1/L3 尚未支持；缺少配对效果与代价政策时不生成最优动作。</p>}
 {decision&&<><strong>风险优先级：{decision.payload.risk.risk_score?.toFixed(3)??`[${decision.payload.risk.lower.toFixed(3)}, ${decision.payload.risk.upper.toFixed(3)}]`} · {STATUS[decision.payload.decision_status]??decision.payload.decision_status}</strong><p>业务价值影响干预代价，不改变风险分数。推荐仅适用于已登记政策与匹配实验，不代表已验证因果机制。</p><details><summary>计算输入、权重与证据</summary><pre>{JSON.stringify(decision.payload.risk.explanation,null,2)}</pre><p>决策工件 {decision.artifact_id}</p><p>推荐实验臂：{decision.payload.recommended_arm_id??"证据不足，未自动推荐"}</p></details>{decision.payload.candidates.filter(c=>c.level===layer).map(c=><article key={c.method_id}><h3>{METHOD_NAMES[c.method_id]??({component_ablation:"组件消融（未支持）",behavior_steering:"行为方向调整（未支持）"} as Record<string,string>)[c.method_id]??c.method_id}</h3><p>{c.objective!==null&&<>政策代价 {c.objective.toFixed(4)} · </>}{c.feasible?"冻结目标与能力已核验":"当前不可执行"} · {c.reasons.map(r=>REASONS[r]??r).join("；")}</p><details><summary>冻结合同与已核验配对证据</summary><pre>{JSON.stringify({contract:c.execution_contract,effect:c.effect_evidence},null,2)}</pre></details><button className="quiet-button" disabled={!allowed||!c.feasible||!c.arm_id||execute.isPending} onClick={()=>execute.mutate(c.arm_id!)}>授权提交冻结实验臂</button></article>)}</>}
 {[save.error,preview.error,execute.error].filter(Boolean).map((e,i)=><p key={i} className="error-text" role="alert">{e?.message}</p>)}
 </div></section>;
}

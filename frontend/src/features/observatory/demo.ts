import type { ExperimentEvent, ExperimentView } from "./model";

/** Design-only fixture: never submitted to any Study, Run or analysis API. */
export function createDemoView(): ExperimentView {
  const identities = ["planner", "sender", "receiver", "tool", "reviewer"];
  const events: ExperimentEvent[] = [];
  const add = (type: string, extra: Partial<ExperimentEvent>) => {
    const seq = events.length + 1;
    events.push({schema_version: "stego.event/1", event_id: `demo:e${seq}`, run_id: "demo-run",
      study_id: "demo-study", arm_id: "baseline", seq, at_utc: `2026-10-29T00:00:${String(seq).padStart(2,"0")}Z`,
      type, provenance: "demo", evidence_refs: ["DEMO:design-fixture"], data: {}, ...extra});
  };
  identities.forEach((actor_id) => add("agent_started", {actor_id}));
  const pairs = [["planner","sender"],["sender","receiver"],["receiver","reviewer"],["tool","receiver"]];
  pairs.forEach(([source_agent_id,target_agent_id],index) => {
    add("message_sent", {source_agent_id,target_agent_id,message_id:`demo:m${index}`});
    add("message_delivered", {source_agent_id,target_agent_id,message_id:`demo:m${index}`});
  });
  add("probe_observed", {actor_id:"receiver",message_id:"demo:m1",data:{value:0.64,label_semantics:"secret_bit"}});
  return {schema_version:"stego.visualization/1",data_mode:"DEMO",origin_mode:"DEMO",workflow_id:"demo-only",
    status:"demo",graph:{schema_version:"stego.graph/1",study_id:"demo-study",run_id:"demo-run",track:"demo",state:"demo",
      nodes:identities.map((id,index)=>({id,label:id==='tool'?'Tool Agent':id[0].toUpperCase()+id.slice(1),role:id,status:"active",source_event_ids:[events[index].event_id]})),
      communication_edges:pairs.map(([source,target],index)=>({id:`${source}->${target}`,source,target,message_ids:[`demo:m${index}`],channel_type:"message",
        delivered_count:1,blocked_count:0,source_event_ids:[events[5+index*2].event_id,events[6+index*2].event_id]})),
      probe_evidence:[{id:events.at(-1)!.event_id,agent_id:"receiver",associated_edge_id:"sender->receiver",value:0.64,
        threshold:0.58,target_layer:12,token_policy:"last_token",label_semantics:"secret_bit",evaluation_split:"DEMO",
        claim_level:"linear_decodability",evidence_refs:["DEMO:design-fixture"]}],interventions:[],evidence_status:"not_run",limitations:["预置示意场景，非实测。"]},
    events,last_seq:events.length,metrics:{},artifacts:[],unavailable_reason:null,limitations:["没有真实秘密恢复率、BER 或防御效果；此场景只用于交互设计。"]};
}

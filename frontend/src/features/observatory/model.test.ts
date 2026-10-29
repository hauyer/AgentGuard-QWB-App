import {describe,it,expect} from "vitest";
import {createDemoView} from "./demo";
import {atSequence,eventSelection,probeThreshold,parseExperimentView,parseComparisonView} from "./model";

describe("public experiment boundary",()=>{
  it("keeps server multiplicity decisions and rejects invalid adjusted probabilities",()=>{
    const report={schema_version:"stego.comparison/2",status:"observed",blockers:[],arms:[],
      multiplicity_method:"holm",adjusted_pvalues:{message_replace:{p_value:.007,adjusted_p_value:.056,reject_at_0_05:false}}};
    expect(parseComparisonView(report).adjusted_pvalues?.message_replace.reject_at_0_05).toBe(false);
    expect(()=>parseComparisonView({...report,adjusted_pvalues:{bad:{p_value:.2,adjusted_p_value:NaN,reject_at_0_05:false}}})).toThrow();
  });
  it("separates Probe observation from positive target-label evidence",()=>{
    const probe={id:"p",agent_id:"receiver",value:.2,threshold:.8,label_semantics:"secret_bit",claim_level:"linear_decodability",evidence_refs:[]};
    expect(probeThreshold(probe)).toBe(false);
    expect(probeThreshold({...probe,value:.8})).toBe(true);
    expect(probeThreshold({...probe,threshold:null})).toBeNull();
  });
  it("never selects an undefined edge for a Run-level event",()=>{
    const event={...createDemoView().events[0],actor_id:null,source_agent_id:null,target_agent_id:null,type:"run_completed"};
    expect(eventSelection(event)).toBeNull();
    expect(eventSelection({...event,source_agent_id:"sender",target_agent_id:"receiver"})).toBe("sender->receiver");
  });
  it("replays monotonically and never creates edges from Probe alone",()=>{
    const view=parseExperimentView(createDemoView());
    expect(atSequence(view,0).communication_edges).toEqual([]);
    const probeOnly={...view,graph:{...view.graph,communication_edges:[]}};
    expect(atSequence(probeOnly,view.last_seq).communication_edges).toEqual([]);
    expect(atSequence(view,view.last_seq)).toEqual(atSequence(view,view.last_seq));
  });
  it("rejects cross-run identity, unknown events and duplicate event ids safely",()=>{
    for(const mutate of [
      (v:ReturnType<typeof createDemoView>)=>{v.events[0].run_id="other";},
      (v:ReturnType<typeof createDemoView>)=>{v.events[0].type="untrusted_future_type";},
      (v:ReturnType<typeof createDemoView>)=>{v.events[1].event_id=v.events[0].event_id;},
      (v:ReturnType<typeof createDemoView>)=>{v.graph.nodes[0].label=undefined as unknown as string;},
    ]){const view=createDemoView();mutate(view);expect(()=>parseExperimentView(view)).toThrow();}
  });
  it("keeps Demo unmeasured and never fills missing outcomes with zero",()=>{
    const view=createDemoView();expect(view.data_mode).toBe("DEMO");expect(view.metrics).toEqual({});
    expect(parseComparisonView({schema_version:"stego.comparison/1",status:"incomplete",blockers:["MISSING"],arms:[]})).toMatchObject({status:"incomplete"});
    expect(()=>parseComparisonView({schema_version:"stego.comparison/1",blockers:[],arms:[{arm_id:"bad",status:"paired",blockers:[],metrics:{BER:{value:NaN,denominator:1}}}]})).toThrow();
  });
});

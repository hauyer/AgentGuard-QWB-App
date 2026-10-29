import {describe,it,expect} from "vitest";
import {createDemoView} from "./demo";
import {atSequence,parseExperimentView,parseComparisonView} from "./model";

describe("public experiment boundary",()=>{
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

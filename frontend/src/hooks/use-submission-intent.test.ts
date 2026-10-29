import {act,renderHook} from "@testing-library/react";
import {beforeEach,describe,it,expect} from "vitest";
import {useSubmissionIntent} from "./use-submission-intent";
describe("durable submission intent",()=>{
  beforeEach(()=>localStorage.clear());
  it("retains an uncertain key through reload and refuses blind new replicates",()=>{
    const first=renderHook(()=>useSubmissionIntent("alice:1:study:batch"));
    const original=first.result.current.intent;
    act(()=>first.result.current.markUncertain());first.unmount();
    const second=renderHook(()=>useSubmissionIntent("alice:1:study:batch"));
    expect(second.result.current.intent.key).toBe(original.key);
    act(()=>second.result.current.newReplicate());
    expect(second.result.current.intent.key).toBe(original.key);
    act(()=>second.result.current.markAccepted());
    act(()=>second.result.current.newReplicate());
    expect(second.result.current.intent.key).not.toBe(original.key);
    expect(second.result.current.intent.replicate_id).not.toBe(original.replicate_id);
  });
  it("isolates scopes and restores the correct accepted intent when switching methods",()=>{
    const hook=renderHook(({scope})=>useSubmissionIntent(scope),{initialProps:{scope:"alice:study:leace"}});
    act(()=>hook.result.current.markAccepted());const original=hook.result.current.intent;
    hook.rerender({scope:"alice:study:block"});
    expect(hook.result.current.intent.key).not.toBe(original.key);
    hook.rerender({scope:"alice:study:leace"});
    expect(hook.result.current.intent).toEqual(original);
  });
});

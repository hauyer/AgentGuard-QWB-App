import { useMemo, useState } from "react";
export type SubmissionIntent={key:string;replicate_id:string;state:"ready"|"uncertain"|"accepted"};
export function createSubmissionIntent():SubmissionIntent {
  const id=crypto.randomUUID();
  return {key:`intent-${id}`,replicate_id:`rep-${id}`,state:"ready"};
}
/** Uncertain submissions retain their key until read-only reconciliation. */
export function useSubmissionIntent(scope:string) {
  const storageKey=`stego-intent/2:${scope}`;
  const stored=useMemo<SubmissionIntent>(()=>{
    try {
      const saved=JSON.parse(localStorage.getItem(storageKey)??"null") as SubmissionIntent|null;
      if(saved?.key&&saved?.replicate_id&&["ready","uncertain","accepted"].includes(saved.state))return saved;
    }catch { /* Invalid browser preferences contain no server state. */ }
    return createSubmissionIntent();
  },[storageKey]);
  const [current,setValue]=useState({scope:storageKey,value:stored});
  const intent=current.scope===storageKey?current.value:stored;
  const save=(value:SubmissionIntent)=>{localStorage.setItem(storageKey,JSON.stringify(value));setValue({scope:storageKey,value});};
  return {intent,markUncertain:()=>save({...intent,state:"uncertain"}),markAccepted:()=>save({...intent,state:"accepted"}),
    newReplicate:()=>{if(intent.state!=="uncertain")save(createSubmissionIntent());}};
}

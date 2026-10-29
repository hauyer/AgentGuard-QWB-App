import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "../services/api";
import { Button } from "./ui/button";
import { useAuthStore } from "../stores/auth-store";

type RunResult = {
  status?: string;
  workflow_id?: string;
  source_validation?: string;
  evidence_mode?: string;
  analysis_status?: string;
  blockers?: string[];
  run?: { run_id?: string; status?: string; updated_at?: string;
    failure?: { code: string; message: string } };
  artifacts?: { artifact_id: string; sha256: string; manifest: unknown }[];
};

export function ResearchRunPanel({ projectId, studyId, study }: {
  projectId: number; studyId: string; study: Record<string, unknown>;
}) {
  const role=useAuthStore(state=>state.role);
  const canSubmit=role==="analyst"||role==="operator"||role==="admin";
  const storageKey = `study-run:${projectId}:${studyId}`;
  const [workflowId, setWorkflowId] = useState(() => localStorage.getItem(storageKey) ?? "");
  const [armId, setArmId] = useState("baseline");
  const arms = Array.isArray(study.arms) ? study.arms as { arm_id: string }[] : [];
  const path = `/projects/${projectId}/studies/${encodeURIComponent(studyId)}/runs`;
  const history = useQuery({
    queryKey: ["study-runs", projectId, studyId],
    queryFn: ({ signal }) => apiGet<{ items: { workflow_id: string }[] }>(path, signal),
  });
  const activeWorkflowId = workflowId || history.data?.items[0]?.workflow_id || "";
  const submit = useMutation({
    mutationFn: () => {
      const keyName = `${storageKey}:submission:${armId}`;
      const key = localStorage.getItem(keyName) ?? crypto.randomUUID();
      localStorage.setItem(keyName, key);
      return apiPost<RunResult>(path, { arm_id: armId }, { "Idempotency-Key": key });
    },
    onSuccess: (result) => {
      if (result.workflow_id) {
        setWorkflowId(result.workflow_id);
        localStorage.setItem(storageKey, result.workflow_id);
      }
    },
  });
  const result = useQuery({
    queryKey: ["study-run", projectId, studyId, activeWorkflowId],
    queryFn: ({ signal }) => apiGet<RunResult>(`${path}/${encodeURIComponent(activeWorkflowId)}`, signal),
    enabled: Boolean(activeWorkflowId),
    refetchInterval: (query) => {
      const state = query.state.data?.run?.status ?? query.state.data?.status;
      return ["completed", "failed", "blocked", "cancelled"].includes(state ?? "") ? false : 3000;
    },
  });
  const data = result.data ?? submit.data;
  const batch=useMutation({mutationFn:()=>{
    const name=`${storageKey}:batch`;const key=localStorage.getItem(name)??crypto.randomUUID();
    localStorage.setItem(name,key);
    return apiPost<{manifest_artifact_id:string;items:{arm_id:string;workflow_id:string;submission:{status:string}}[]}>(`/projects/${projectId}/studies/${encodeURIComponent(studyId)}/run-batches`,undefined,{"Idempotency-Key":key});
  },onSettled:()=>void batches.refetch()});
  const batches=useQuery({queryKey:["study-batches",projectId,studyId],
    queryFn:({signal})=>apiGet<{items:{batch_id:string;manifest_artifact_id:string;items:{arm_id:string;run_id:string|null;submission_status:string}[]}[]}>(`/projects/${projectId}/studies/${encodeURIComponent(studyId)}/run-batches`,signal)});
  const error = result.error ?? submit.error ?? history.error;
  return <section className="min-w-0 space-y-2 rounded-md border border-surface-border p-3">
    <h3 className="text-sm font-semibold">真实实验运行</h3>
    <div className="flex flex-wrap gap-2">
      <select aria-label="实验臂" value={armId} onChange={(event) => setArmId(event.target.value)}
        className="max-w-full rounded border p-1" disabled={submit.isPending || Boolean(workflowId)}>
        {arms.map((arm) => <option key={arm.arm_id} value={arm.arm_id}>{arm.arm_id}</option>)}
      </select>
      <Button disabled={!canSubmit || !arms.length || submit.isPending || Boolean(workflowId)}
        onClick={() => submit.mutate()}>{submit.isPending ? "提交中…" : "提交实验"}</Button>
      {activeWorkflowId && <Button onClick={() => void result.refetch()}>刷新状态</Button>}
      <Button variant="secondary" disabled={!canSubmit||!arms.length||batch.isPending} onClick={()=>batch.mutate()}>{batch.isPending?"正在登记批次…":"提交全部冻结实验臂"}</Button>
    </div>
    {error && <p role="alert" className="break-words text-xs text-red-700">{error.message}</p>}
    {batch.error&&<p role="alert">{batch.error.message}。提交结果可能不确定：先查询批次历史；重复提交使用已保存的同一幂等键。</p>}
    <details><summary>已保存批次历史（{batches.data?.items.length??0}）</summary><Button variant="secondary" onClick={()=>void batches.refetch()}>查询批次历史</Button>{batches.data?.items.map(item=><div key={item.batch_id}><p className="break-all">{item.batch_id}</p><p className="break-all">SHA-256：{item.manifest_artifact_id}</p>{item.items.map(arm=><p key={arm.arm_id} className="break-all">{arm.arm_id} · {arm.submission_status} · {arm.run_id??"尚未提交"}</p>)}</div>)}</details>
    {batch.data&&<details><summary>批次清单已保存 · {batch.data.items.length} 个实验臂</summary><p className="break-all">工件：{batch.data.manifest_artifact_id}</p>{batch.data.items.map(item=><p key={item.arm_id} className="break-all">{item.arm_id} · {item.submission.status} · {item.workflow_id}</p>)}</details>}
    {!data && <p className="text-xs text-slate-500">尚未产生运行结果。</p>}
    {data && <div className="space-y-1 break-all text-xs">
      <p>状态：{data.run?.status ?? data.status ?? "unknown"}</p>
      <p>任务：{data.run?.run_id ?? workflowId ?? "尚未分配"}</p>
      <p>更新时间：{data.run?.updated_at ?? "尚未返回"}</p>
      <p>来源：{data.evidence_mode ?? "尚未核验"}；校验：{data.source_validation ?? "尚未核验"}</p>
      <p>分析：{data.analysis_status ?? "尚未产生"}</p>
      {data.run?.failure && <p role="alert">{data.run.failure.code}：{data.run.failure.message}</p>}
      {data.blockers?.map((blocker) => <p key={blocker}>{blocker}</p>)}
      {data.artifacts?.map((artifact) => <details key={artifact.artifact_id}>
        <summary>已核验工件 {artifact.artifact_id}</summary>
        <p>SHA-256：{artifact.sha256}</p>
        <pre className="max-h-64 max-w-full overflow-auto whitespace-pre-wrap">{JSON.stringify(artifact.manifest, null, 2)}</pre>
      </details>)}
    </div>}
  </section>;
}

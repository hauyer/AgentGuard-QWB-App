import { useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../ui/button";

export function ResourcePicker({value, onSelect, kind}: {
  value: string; onSelect: (value: string) => void; kind: "investigation" | "run";
}) {
  const id=useId();
  const [draft,setDraft]=useState(value);
  useEffect(()=>setDraft(value),[value]);
  const label=kind==="run"?"调查运行 ID":"调查 ID";
  return <><form className="resource-picker" aria-label={`选择${label}`} onSubmit={event=>{event.preventDefault();onSelect(draft);}}>
    <label htmlFor={id}>{label}<input id={id} value={draft} onChange={event=>setDraft(event.target.value)}
      placeholder={`输入已有${label}`} maxLength={256} pattern="[A-Za-z0-9._:-]+" autoComplete="off" required/></label>
    <Button type="submit" disabled={!draft.trim()}>载入记录</Button>
    {value&&<Button variant="secondary" onClick={()=>onSelect("")}>清除选择</Button>}
    <p>使用已有调查的编号读取记录。<Link to="/investigations">前往安全调查</Link>；真实研究的通信与配对结果请从侧栏的结果分析台查看。</p>
  </form>{!value&&<div className="resource-empty" role="status">尚未选择{label}。从安全调查中打开已有记录，或输入已知编号，查看对应证据与报告。</div>}</>;
}

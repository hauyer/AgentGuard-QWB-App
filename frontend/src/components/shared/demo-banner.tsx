import { PlayCircle } from "lucide-react";

import { Badge } from "../ui/badge";
import type { MetaInfo } from "../../types/dashboard";

/**
 * Explicit replay marker for RECORDED/SYNTHETIC data. Demo data must always be
 * visibly distinguishable from a live backend, so every page that can show
 * fixture data renders this banner with the fixture provenance.
 */
export function DemoBanner({ meta }: { meta: MetaInfo }) {
  if (meta.data_mode === "live" || meta.data_mode === "unavailable") return null;
  const modeLabel = meta.data_mode === "recorded" ? "RECORDED 回放" : "SYNTHETIC 演示";
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <PlayCircle aria-hidden className="h-4 w-4 text-violet-600" />
        <span className="font-medium text-violet-800">{modeLabel}：当前数据来自演示样例，不是实时后端</span>
        {meta.fixture_id && (
          <Badge variant="neutral" className="font-mono">
            {meta.fixture_id}
          </Badge>
        )}
        {meta.sanitized && <Badge variant="neutral">已脱敏</Badge>}
      </div>
      {meta.source && <p className="text-xs text-violet-700">来源：{meta.source}</p>}
      {meta.not_provable && meta.not_provable.length > 0 && (
        <ul className="list-inside list-disc text-xs text-violet-700">
          {meta.not_provable.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

import {
  AlertTriangle,
  BarChart3,
  BookOpenText,
  FlaskConical,
  FolderKanban,
  HelpCircle,
  LayoutDashboard,
  Network,
  PlayCircle,
  ScrollText,
  Settings,
  ShieldCheck,
  Swords,
  Target,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { useSystemStatus } from "../../hooks/use-system-status";
import { cn } from "../../utils/cn";
import { Badge } from "../ui/badge";
import { StatusDot } from "../ui/status-dot";
import { SessionControl } from "./SessionControl";

const NAV_ITEMS = [
  { to: "/", label: "系统总览", icon: LayoutDashboard, end: true },
  { to: "/demo", label: "演示导览", icon: PlayCircle },
  { to: "/projects", label: "项目管理", icon: FolderKanban },
  { to: "/investigations", label: "安全调查", icon: Target },
  { to: "/interaction-graph", label: "交互图谱", icon: Network },
  { to: "/evidence", label: "证据分析", icon: ScrollText },
  { to: "/findings", label: "风险发现", icon: AlertTriangle },
  { to: "/hypotheses", label: "调查假设", icon: HelpCircle },
  { to: "/investigation-journal", label: "多轮调查", icon: Target },
  { to: "/defenses", label: "定向防御", icon: ShieldCheck },
  { to: "/experiments", label: "实验对比", icon: FlaskConical },
  { to: "/experiences", label: "经验中心", icon: BookOpenText },
  { to: "/reports", label: "报告中心", icon: BarChart3 },
  { to: "/settings", label: "系统设置", icon: Settings },
];

function dataModeLabel(mode: string): string {
  switch (mode) {
    case "live":
      return "LIVE";
    case "recorded":
      return "RECORDED";
    case "synthetic":
      return "SYNTHETIC";
    case "unavailable":
      return "UNAVAILABLE";
    default:
      return mode.toUpperCase();
  }
}

export function AppLayout() {
  const { data } = useSystemStatus();
  const agentguardReachable = data?.agentguard.reachable;
  const syntheticBackend = data?.agentguard.capabilities?.backend_mode?.toLowerCase() === "synthetic";

  return (
    <div className="flex h-full min-h-screen">
      <aside className="flex w-56 shrink-0 flex-col border-r border-surface-border bg-white">
        <div className="flex h-14 items-center gap-2 border-b border-surface-border px-4">
          <Swords className="h-5 w-5 text-brand-600" />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-slate-800">AgentGuard-QWB</div>
            <div className="text-[11px] text-slate-500">多智能体安全审计平台</div>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-slate-600 transition-colors",
                  isActive ? "bg-brand-50 font-medium text-brand-700" : "hover:bg-surface-muted",
                )
              }
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-surface-border p-3 text-[11px] text-slate-400">
          强网杯应用平台 · B0 基线
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-surface-border bg-white px-4">
          <div className="flex items-center gap-3 text-sm text-slate-600">
            <span>当前项目：AgentGuard-QWB-App</span>
            <Badge variant={data?.data_mode === "live" ? "ok" : "neutral"}>
              {data ? dataModeLabel(data.data_mode) : "…"}
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1.5 text-slate-600">
              <StatusDot tone={agentguardReachable === undefined ? "neutral" : agentguardReachable ? "ok" : "danger"} />
              AgentGuard {agentguardReachable ? "已连接" : agentguardReachable === undefined ? "检测中" : "不可用"}
            </span>
            <SessionControl />
          </div>
        </header>
        <main className="min-w-0 flex-1 overflow-y-auto p-6">
          {syntheticBackend && (
            <div
              role="status"
              data-testid="synthetic-backend-banner"
              className="mb-4 rounded-md border border-violet-200 bg-violet-50 px-4 py-3 text-xs text-violet-800"
            >
              当前 AgentGuard backend_mode 为 SYNTHETIC。这里的 Stub 数据仅用于合同与流程验证，不代表真实 WARDEN、模型运行或实验结果。
            </div>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  );
}

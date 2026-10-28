import {
  AlertTriangle,
  BarChart3,
  BookOpenText,
  FlaskConical,
  FolderKanban,
  HelpCircle,
  LayoutDashboard,
  Menu,
  Network,
  PlayCircle,
  ScrollText,
  Settings,
  ShieldCheck,
  Swords,
  Target,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useMatches } from "react-router-dom";

import { useSystemStatus } from "../../hooks/use-system-status";
import { cn } from "../../utils/cn";
import { Badge } from "../ui/badge";
import { StatusDot } from "../ui/status-dot";
import { SessionControl } from "./SessionControl";

const NAV_GROUPS = [
  {
    label: "工作区",
    items: [
      { to: "/", label: "系统总览", icon: LayoutDashboard, end: true },
      { to: "/projects", label: "项目管理", icon: FolderKanban },
      { to: "/investigations", label: "安全调查", icon: Target },
      { to: "/investigation-journal", label: "多轮工作台", icon: BookOpenText },
      { to: "/research", label: "研究工作台", icon: FlaskConical },
      { to: "/demo", label: "演示导览", icon: PlayCircle },
    ],
  },
  {
    label: "调查分析",
    items: [
      { to: "/interaction-graph", label: "交互图谱", icon: Network },
      { to: "/evidence", label: "证据分析", icon: ScrollText },
      { to: "/findings", label: "风险发现", icon: AlertTriangle },
      { to: "/hypotheses", label: "调查假设", icon: HelpCircle },
    ],
  },
  {
    label: "研究与响应",
    items: [
      { to: "/strategy-comparison", label: "策略评价", icon: BarChart3 },
      { to: "/experiments", label: "实验对比", icon: FlaskConical },
      { to: "/experiences", label: "经验中心", icon: BookOpenText },
      { to: "/defenses", label: "定向防御", icon: ShieldCheck },
      { to: "/reports", label: "报告中心", icon: ScrollText },
    ],
  },
  {
    label: "系统",
    items: [{ to: "/settings", label: "系统设置", icon: Settings }],
  },
];

function dataModeLabel(mode: string): string {
  switch (mode) {
    case "live": return "LIVE";
    case "recorded": return "RECORDED";
    case "synthetic": return "SYNTHETIC";
    case "unavailable": return "UNAVAILABLE";
    default: return mode.toUpperCase();
  }
}

function connectionStatusLabel(synthetic: boolean, reachable: boolean | undefined): string {
  if (synthetic) return reachable ? "AgentGuard Stub 已连接" : "AgentGuard Stub 不可用";
  if (reachable === undefined) return "检查连接";
  return reachable ? "AgentGuard 已连接" : "AgentGuard 不可用";
}

function Brand() {
  return (
    <div className="flex h-16 items-center gap-3 border-b border-surface-border px-5">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-950 text-white">
        <Swords className="h-[18px] w-[18px]" />
      </span>
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold tracking-tight text-slate-900">AgentGuard QWB</div>
        <div className="text-[10px] tracking-[0.12em] text-slate-500">SECURITY WORKSPACE</div>
      </div>
    </div>
  );
}

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="主导航" className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {NAV_GROUPS.map((group) => (
        <section key={group.label}>
          <h2 className="mb-1.5 px-3 text-[10px] font-semibold tracking-[0.12em] text-slate-400">
            {group.label}
          </h2>
          <div className="space-y-0.5">
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onNavigate}
                className={({ isActive }) => cn(
                  "group flex min-h-9 items-center gap-3 rounded-md px-3 text-[13px] transition-colors",
                  isActive
                    ? "bg-brand-50 font-medium text-brand-700 ring-1 ring-inset ring-brand-100"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                )}
              >
                <item.icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        </section>
      ))}
    </nav>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-surface-border bg-white">
      <Brand />
      <Navigation onNavigate={onNavigate} />
      <div className="border-t border-surface-border px-5 py-3 text-[10px] text-slate-400">
        强网杯 · 调查与审计
      </div>
    </aside>
  );
}

export function AppLayout() {
  const { data } = useSystemStatus();
  const matches = useMatches();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const agentguardReachable = data?.agentguard.reachable;
  const syntheticBackend = data?.agentguard.capabilities?.backend_mode?.toLowerCase() === "synthetic";
  const pageTitle = [...matches].reverse().find((match) => {
    const title = (match.handle as { title?: unknown } | undefined)?.title;
    return typeof title === "string";
  });
  const displayedPageTitle = (pageTitle?.handle as { title: string } | undefined)?.title ?? "AgentGuard QWB";
  const displayedDataMode = syntheticBackend ? "synthetic" : data?.data_mode;
  const connectionLabel = connectionStatusLabel(syntheticBackend, agentguardReachable);

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="presentation">
          <button
            type="button"
            aria-label="关闭导航"
            className="absolute inset-0 bg-slate-950/35"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="relative h-full w-[min(18rem,86vw)] shadow-2xl">
            <button
              type="button"
              aria-label="关闭导航"
              onClick={() => setMobileMenuOpen(false)}
              className="absolute right-3 top-4 z-10 rounded-md p-2 text-slate-500 hover:bg-slate-100"
            >
              <X className="h-4 w-4" />
            </button>
            <Sidebar onNavigate={() => setMobileMenuOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between border-b border-surface-border bg-white/95 px-3 backdrop-blur sm:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              aria-label="打开导航"
              aria-expanded={mobileMenuOpen}
              onClick={() => setMobileMenuOpen(true)}
              className="rounded-md p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-800">{displayedPageTitle}</p>
              <p className="hidden text-[10px] text-slate-400 sm:block">AgentGuard · QWB 安全调查工作台</p>
            </div>
            <Badge variant={displayedDataMode === "live" ? "ok" : "neutral"}>
              {displayedDataMode ? dataModeLabel(displayedDataMode) : "检测中"}
            </Badge>
          </div>
          <div className="flex shrink-0 items-center gap-3 sm:gap-4">
            <span className="hidden items-center gap-1.5 text-xs text-slate-600 sm:flex">
              <StatusDot tone={agentguardReachable === undefined ? "neutral" : agentguardReachable ? "ok" : "danger"} />
              {connectionLabel}
            </span>
            <SessionControl />
          </div>
        </header>
        <main className="min-w-0 flex-1 p-3 sm:p-5 lg:p-7">
          {syntheticBackend && (
            <div
              role="status"
              data-testid="synthetic-backend-banner"
              className="mb-4 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-800"
            >
              <strong className="font-semibold">SYNTHETIC 数据源</strong>
              <span>Stub 用于合同与流程验证，不代表真实 WARDEN、模型运行或实验结果。</span>
            </div>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  );
}

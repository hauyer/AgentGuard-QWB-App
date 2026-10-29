import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, BarChart3, BookOpenText, ChevronRight, FileCheck2, FlaskConical, FolderKanban,
  Layers3, Menu, Network, Search, Settings, Shield, X } from "lucide-react";
import { Link, NavLink, Outlet, useLocation, useMatches } from "react-router-dom";
import { useSystemStatus } from "../../hooks/use-system-status";
import { useAuthStore } from "../../stores/auth-store";
import { SessionControl } from "./SessionControl";
import type { WorkspaceChrome } from "./workspace-context";
import "../../features/observatory/observatory.css";
import "./workspace.css";

const EXPERIMENT_PATHS = new Set(["/sandbox", "/detection", "/intervention-lab", "/analysis", "/research"]);
const CONTEXT_KEYS = ["projectId", "studyId", "workflowId", "mode"];
const MAIN_NAV = [
  { to: "/sandbox", label: "总控台", icon: Activity }, { to: "/detection", label: "通信检测台", icon: Network },
  { to: "/intervention-lab", label: "干预实验台", icon: Shield }, { to: "/analysis", label: "结果分析台", icon: BarChart3 },
  { to: "/research", label: "研究管理", icon: FlaskConical },
];
const MANAGEMENT_NAV = [
  { to: "/projects", label: "项目管理", icon: FolderKanban }, { to: "/reports", label: "证据与报告", icon: FileCheck2 },
  { to: "/investigations", label: "安全调查", icon: Search }, { to: "/system-overview", label: "系统与诊断", icon: Activity },
];
const TOOLS_NAV = [
  { to: "/interaction-graph", label: "交互图谱", icon: Network }, { to: "/evidence", label: "证据分析", icon: FileCheck2 },
  { to: "/findings", label: "风险发现", icon: Search }, { to: "/hypotheses", label: "调查假设", icon: Search },
  { to: "/investigation-journal", label: "多轮工作台", icon: BookOpenText }, { to: "/defenses", label: "定向防御", icon: Shield },
  { to: "/experiments", label: "实验对比", icon: FlaskConical }, { to: "/strategy-comparison", label: "策略评价", icon: BarChart3 },
  { to: "/experiences", label: "经验中心", icon: BookOpenText }, { to: "/multi-round-report", label: "多轮报告", icon: FileCheck2 },
  { to: "/demo", label: "演示导览", icon: Layers3 }, { to: "/settings", label: "系统设置", icon: Settings },
];
function contextSearch(search: string): string {
  const source = new URLSearchParams(search), result = new URLSearchParams();
  CONTEXT_KEYS.forEach(key => { const value = source.get(key); if (value) result.set(key, value); });
  return result.size ? `?${result}` : "";
}

/** The same frame remains mounted across all workbench and management routes. */
export function AppLayout() {
  const location = useLocation(), matches = useMatches();
  const [menuOpen, setMenuOpen] = useState(false), [savedSearch, setSavedSearch] = useState("");
  const [sourceState, setSourceState] = useState<{path: string; label: string | null} | null>(null);
  const source = sourceState?.path === location.pathname ? sourceState.label : null;
  const setSource = useCallback((value: string | null) => setSourceState({path: location.pathname, label: value}), [location.pathname]);
  const user = useAuthStore(state => state.username), authStatus = useAuthStore(state => state.status);
  const lastUser = useRef<string | null | undefined>(undefined);
  const previousPath = useRef(location.pathname);
  const menuButton = useRef<HTMLButtonElement>(null), sidebar = useRef<HTMLElement>(null);
  const system = useSystemStatus();
  const isExperiment = EXPERIMENT_PATHS.has(location.pathname);
  const experimentSearch = isExperiment ? contextSearch(location.search) : savedSearch;
  const title = [...matches].reverse().map(match => (match.handle as {title?: string} | undefined)?.title).find(Boolean) ?? "页面不存在";
  const synthetic = system.data?.agentguard.capabilities?.backend_mode?.toLowerCase() === "synthetic";

  useEffect(() => { if (isExperiment) setSavedSearch(contextSearch(location.search)); }, [isExperiment, location.search]);
  useEffect(() => {
    if (authStatus !== "ready") return;
    if (lastUser.current !== undefined && lastUser.current !== user) setSavedSearch("");
    lastUser.current = user;
  }, [user, authStatus]);
  useEffect(() => {
    setMenuOpen(false);document.title=`${title} · StegoSandbox`;
    if(previousPath.current!==location.pathname){document.querySelector<HTMLElement>("#workspace-content")?.focus({preventScroll:true});document.documentElement.scrollTop=0;}
    previousPath.current=location.pathname;
  }, [location.pathname,title]);
  useEffect(() => {
    if (!window.matchMedia) return;
    const media = window.matchMedia("(max-width: 760px)");
    const sync = () => { if (sidebar.current) sidebar.current.inert = media.matches && !menuOpen; };
    sync(); media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, [menuOpen]);
  useEffect(() => {
    if (!menuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sidebar.current?.querySelector<HTMLElement>("a")?.focus();
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setMenuOpen(false); menuButton.current?.focus(); }
      if (event.key !== "Tab") return;
      const targets = [...(sidebar.current?.querySelectorAll<HTMLElement>("a,button,summary") ?? [])].filter(item => item.getClientRects().length);
      const first = targets[0], last = targets.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    const resized = () => { if (window.innerWidth > 760) setMenuOpen(false); };
    window.addEventListener("keydown", keyboard); window.addEventListener("resize", resized);
    return () => { document.body.style.overflow = previousOverflow; window.removeEventListener("keydown", keyboard); window.removeEventListener("resize", resized); };
  }, [menuOpen]);
  const renderLink = (item: typeof MAIN_NAV[number], experiment = false) => <NavLink
    key={item.to} to={`${item.to}${experiment ? experimentSearch : ""}`} end={item.to !== "/investigations"}
    onClick={() => setMenuOpen(false)} className={({isActive}) => isActive ? "active" : ""}>
    <item.icon size={17} aria-hidden="true"/><span>{item.label}</span><ChevronRight className="nav-chevron" size={13} aria-hidden="true"/>
  </NavLink>;
  return <div className="stego-shell workspace-shell" data-app-shell="workspace">
    <a className="skip-to-content" href="#workspace-content">跳至页面内容</a>
    <aside ref={sidebar} id="workspace-sidebar" className={`stego-sidebar ${menuOpen ? "is-open" : ""}`} aria-label="工作区侧栏">
      <Link to={`/sandbox${experimentSearch}`} className="stego-brand" aria-label="StegoSandbox 总控台"><span><Layers3 size={21}/></span><div>Stego<span className="brand-light">Sandbox</span><small>AGENT SECURITY LABORATORY</small></div></Link>
      <button className="icon-button sidebar-close" aria-label="关闭导航" onClick={() => {setMenuOpen(false); menuButton.current?.focus();}}><X size={18}/></button>
      <nav aria-label="主导航" className="workspace-navigation">
        <p className="nav-label">实验工作区</p>{MAIN_NAV.map(item => renderLink(item, true))}
        <p className="nav-label">管理与证据</p>{MANAGEMENT_NAV.map(item => renderLink(item))}
        <details className="workspace-tools" key={TOOLS_NAV.some(item => item.to === location.pathname) ? location.pathname : "tools"} open={TOOLS_NAV.some(item => item.to === location.pathname)}>
          <summary>更多调查工具<ChevronRight size={13}/></summary>{TOOLS_NAV.map(item => renderLink(item))}
        </details>
      </nav>
      <div className="sidebar-note"><span className="status-dot"/>证据可追溯 · 结果可复核<small>OBSERVE / INTERVENE / VERIFY</small></div>
    </aside>
    {menuOpen && <button className="sidebar-scrim" aria-label="收起导航遮罩" onClick={() => setMenuOpen(false)}/>}
    <div className="stego-main">
      <header className="stego-topbar">
        <button ref={menuButton} className="icon-button mobile-menu" aria-label="打开导航" aria-expanded={menuOpen} aria-controls="workspace-sidebar" onClick={() => setMenuOpen(!menuOpen)}><Menu size={19}/></button>
        <div className="breadcrumb"><span>{isExperiment ? "实验工作区" : "管理与证据"}</span><ChevronRight size={12}/><strong>{title}</strong></div>
        <div className="top-context"><span className={`source-badge ${source === "DEMO" ? "demo" : source === "UNAVAILABLE" && isExperiment ? "unavailable" : !source || !isExperiment || source === "读取中" || source === "未选择运行" ? "pending" : ""}`}>{isExperiment ? source ?? "研究工作区" : location.pathname === "/projects" ? "项目数据" : "审计与管理"}</span><div className="observatory-session"><SessionControl/></div></div>
      </header>
      <main id="workspace-content" className={`stego-content ${isExperiment ? "experiment-content" : "management-content"}`} tabIndex={-1}>
        {["/reports","/evidence","/findings","/multi-round-report"].includes(location.pathname)&&<nav className="workspace-section-tabs" aria-label="证据与报告导航"><Link to={`/analysis${savedSearch}`}>研究结果与工件</Link><NavLink to="/reports">调查报告</NavLink><NavLink to="/evidence">调查证据</NavLink><NavLink to="/multi-round-report">多轮报告</NavLink></nav>}
        {["/system-overview","/settings"].includes(location.pathname)&&<nav className="workspace-section-tabs" aria-label="系统页面导航"><NavLink to="/system-overview">服务诊断</NavLink><NavLink to="/settings">设置与权限</NavLink></nav>}
        {synthetic && <details className="workspace-provenance" data-testid="synthetic-backend-banner"><summary>通用审计使用测试数据；研究结果按独立工件核验</summary><p>通用审计使用测试后端，不代表真实 WARDEN、模型运行或实验结果；独立研究任务以各自的运行来源和工件校验为准。</p></details>}
        <Outlet context={{setSource} satisfies WorkspaceChrome}/>
      </main>
      <footer className="stego-footer"><span><FileCheck2 size={12}/>StegoSandbox · 可追溯实验工作区</span><span>{source === "DEMO" && isExperiment ? "示意数据不构成研究发现" : "通信事实 / 表示证据 / 行为验证"}</span></footer>
    </div>
  </div>;
}

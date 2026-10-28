import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "../components/layout/AppLayout";
import { CreateInvestigationPage } from "../pages/CreateInvestigationPage";
import { DefensePage } from "../pages/DefensePage";
import { DemoCenterPage } from "../pages/DemoCenterPage";
import { EvidencePage } from "../pages/EvidencePage";
import { ExperiencesPage } from "../pages/ExperiencesPage";
import { ExperimentsPage } from "../pages/ExperimentsPage";
import { FindingsPage } from "../pages/FindingsPage";
import { HypothesesPage } from "../pages/HypothesesPage";
import { InteractionGraphPage } from "../pages/InteractionGraphPage";
import { InvestigationDetailPage } from "../pages/InvestigationDetailPage";
import { InvestigationJournalPage } from "../pages/InvestigationJournalPage";
import { InvestigationWorkspacePage } from "../pages/InvestigationWorkspacePage";
import { InvestigationsListPage } from "../pages/InvestigationsListPage";
import { MultiRoundReportPage } from "../pages/MultiRoundReportPage";
import { ProjectsPage } from "../pages/ProjectsPage";
import { ReportsPage } from "../pages/ReportsPage";
import { ResearchWorkbenchPage } from "../pages/ResearchWorkbenchPage";
import { SettingsPage } from "../pages/SettingsPage";
import { SystemOverviewPage } from "../pages/SystemOverviewPage";
import { StrategyComparisonPage } from "../pages/StrategyComparisonPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <SystemOverviewPage />, handle: { title: "系统总览" } },
      { path: "demo", element: <DemoCenterPage />, handle: { title: "演示导览" } },
      { path: "investigations", element: <InvestigationsListPage />, handle: { title: "安全调查" } },
      { path: "projects", element: <ProjectsPage />, handle: { title: "项目管理" } },
      { path: "investigations/new", element: <CreateInvestigationPage />, handle: { title: "创建调查" } },
      { path: "investigations/:requestId", element: <InvestigationDetailPage />, handle: { title: "调查详情" } },
      { path: "investigations/:requestId/workspace", element: <InvestigationWorkspacePage />, handle: { title: "调查工作区" } },
      { path: "interaction-graph", element: <InteractionGraphPage />, handle: { title: "交互图谱" } },
      { path: "evidence", element: <EvidencePage />, handle: { title: "证据分析" } },
      { path: "findings", element: <FindingsPage />, handle: { title: "风险发现" } },
      { path: "hypotheses", element: <HypothesesPage />, handle: { title: "调查假设" } },
      { path: "investigation-journal", element: <InvestigationJournalPage />, handle: { title: "多轮工作台" } },
      { path: "defenses", element: <DefensePage />, handle: { title: "定向防御" } },
      { path: "research", element: <ResearchWorkbenchPage />, handle: { title: "研究工作台" } },
      { path: "experiments", element: <ExperimentsPage />, handle: { title: "实验对比" } },
      { path: "strategy-comparison", element: <StrategyComparisonPage />, handle: { title: "策略评价" } },
      { path: "experiences", element: <ExperiencesPage />, handle: { title: "经验中心" } },
      { path: "reports", element: <ReportsPage />, handle: { title: "报告中心" } },
      { path: "multi-round-report", element: <MultiRoundReportPage />, handle: { title: "多轮报告" } },
      { path: "settings", element: <SettingsPage />, handle: { title: "系统设置" } },
    ],
  },
]);

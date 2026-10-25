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
import { InvestigationWorkspacePage } from "../pages/InvestigationWorkspacePage";
import { InvestigationsListPage } from "../pages/InvestigationsListPage";
import { ProjectsPage } from "../pages/ProjectsPage";
import { ReportsPage } from "../pages/ReportsPage";
import { SettingsPage } from "../pages/SettingsPage";
import { SystemOverviewPage } from "../pages/SystemOverviewPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <SystemOverviewPage /> },
      { path: "demo", element: <DemoCenterPage /> },
      { path: "investigations", element: <InvestigationsListPage /> },
      { path: "projects", element: <ProjectsPage /> },
      { path: "investigations/new", element: <CreateInvestigationPage /> },
      { path: "investigations/:requestId", element: <InvestigationDetailPage /> },
      { path: "investigations/:requestId/workspace", element: <InvestigationWorkspacePage /> },
      { path: "interaction-graph", element: <InteractionGraphPage /> },
      { path: "evidence", element: <EvidencePage /> },
      { path: "findings", element: <FindingsPage /> },
      { path: "hypotheses", element: <HypothesesPage /> },
      { path: "defenses", element: <DefensePage /> },
      { path: "experiments", element: <ExperimentsPage /> },
      { path: "experiences", element: <ExperiencesPage /> },
      { path: "reports", element: <ReportsPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);

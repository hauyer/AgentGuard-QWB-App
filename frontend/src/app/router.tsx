import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "../components/layout/AppLayout";
import { PlaceholderPage } from "../pages/PlaceholderPage";
import { SystemOverviewPage } from "../pages/SystemOverviewPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <SystemOverviewPage /> },
      { path: "investigations", element: <PlaceholderPage title="安全调查" stage="B3" /> },
      { path: "interaction-graph", element: <PlaceholderPage title="交互图谱" stage="B4" /> },
      { path: "evidence", element: <PlaceholderPage title="证据分析" stage="B5" /> },
      { path: "defenses", element: <PlaceholderPage title="定向防御" stage="B5" /> },
      { path: "experiments", element: <PlaceholderPage title="实验对比" stage="B6" /> },
      { path: "experiences", element: <PlaceholderPage title="经验中心" stage="B6" /> },
      { path: "reports", element: <PlaceholderPage title="报告中心" stage="B6" /> },
      { path: "settings", element: <PlaceholderPage title="系统设置" stage="B8" /> },
    ],
  },
]);

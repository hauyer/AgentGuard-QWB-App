import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EvidenceLevelBadge } from "../shared/evidence-level-badge";
import { VerificationBadge } from "../shared/verification-badge";
import { SourceBadge } from "../shared/source-badge";
import { MetricCard } from "../shared/metric-card";
import { InvestigationTimeline } from "../shared/investigation-timeline";
import { PermissionGate } from "../shared/permission-gate";
import { EmptyState } from "../ui/empty-state";
import { LoadingState } from "../ui/loading-state";
import { ErrorState } from "../ui/error-state";
import { Pagination } from "../ui/pagination";
import { JsonViewer } from "../ui/json-viewer";
import { useAuthStore } from "../../stores/auth-store";

describe("shared design system components", () => {
  describe("evidence level badge", () => {
    it("labels every evidence level without implying causality", () => {
      render(<EvidenceLevelBadge level="synthetic" />);
      expect(screen.getByText("SYNTHETIC")).toBeInTheDocument();
    });
    it("marks causal_validated distinctly", () => {
      render(<EvidenceLevelBadge level="causal_validated" />);
      expect(screen.getByText("CAUSAL_VALIDATED")).toBeInTheDocument();
    });
    it("renders unknown levels safely", () => {
      render(<EvidenceLevelBadge level="unknown" />);
      expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
    });
  });

  describe("verification badge", () => {
    it("renders verified and unverified labels", () => {
      render(<VerificationBadge status="verified" />);
      expect(screen.getByText("已验证")).toBeInTheDocument();
      render(<VerificationBadge status="unverified" />);
      expect(screen.getByText("未验证")).toBeInTheDocument();
    });
  });

  describe("source badge", () => {
    it("labels live AgentGuard data", () => {
      render(<SourceBadge source="agentguard" />);
      expect(screen.getByText("agentguard")).toBeInTheDocument();
    });
    it("labels fixture-sourced data", () => {
      render(<SourceBadge source="fixture:fx-inv-001" />);
      expect(screen.getByText("fixture:fx-inv-001")).toBeInTheDocument();
    });
  });

  describe("metric card", () => {
    it("shows an explicit unavailable state instead of a fabricated value", () => {
      render(<MetricCard title="调查总数" unavailable />);
      expect(screen.getByText("调查总数")).toBeInTheDocument();
      expect(screen.getByText("不可用")).toBeInTheDocument();
    });
    it("renders a real value", () => {
      render(<MetricCard title="运行中" value="3" />);
      expect(screen.getByText("3")).toBeInTheDocument();
    });
  });

  describe("investigation timeline", () => {
    it("marks confirmed steps and keeps unconfirmed steps pending with a hint", () => {
      render(
        <InvestigationTimeline
          events={[
            { step: "created", label: "调查创建", status: "completed", at: "2026-10-23T08:00:00Z" },
            { step: "planned", label: "审计计划", status: "pending" },
          ]}
        />,
      );
      expect(screen.getByText("调查创建")).toBeInTheDocument();
      expect(screen.getByText("审计计划")).toBeInTheDocument();
      expect(screen.getByText(/未确认/)).toBeInTheDocument();
    });
  });

  describe("permission gate", () => {
    beforeEach(() => {
      useAuthStore.getState().setSession({ role: "viewer", authEnabled: true });
    });
    it("blocks when the role is insufficient", () => {
      render(
        <PermissionGate required="analyst">
          <div>机密内容</div>
        </PermissionGate>,
      );
      expect(screen.getByText("权限不足")).toBeInTheDocument();
      expect(screen.queryByText("机密内容")).not.toBeInTheDocument();
    });
    it("allows when the role is sufficient", () => {
      useAuthStore.getState().setSession({ role: "operator", authEnabled: true });
      render(
        <PermissionGate required="analyst">
          <div>机密内容</div>
        </PermissionGate>,
      );
      expect(screen.getByText("机密内容")).toBeInTheDocument();
      expect(screen.queryByText("权限不足")).not.toBeInTheDocument();
    });
  });

  describe("empty / loading states", () => {
    it("renders empty state", () => {
      render(<EmptyState title="暂无调查" description="创建第一个调查" />);
      expect(screen.getByText("暂无调查")).toBeInTheDocument();
    });
    it("renders loading state with role=status", () => {
      render(<LoadingState label="加载中" />);
      expect(screen.getByRole("status")).toBeInTheDocument();
    });
  });

  describe("error state", () => {
    it("renders backend-unavailable with error code and request id", () => {
      render(<ErrorState kind="backend" code="API_UNREACHABLE" requestId="req-abc" message="连接被拒绝" />);
      expect(screen.getByText("连接被拒绝")).toBeInTheDocument();
      expect(screen.getByText(/API_UNREACHABLE/)).toBeInTheDocument();
      expect(screen.getByText(/req-abc/)).toBeInTheDocument();
    });
    it("renders permission-denied state", () => {
      render(<ErrorState kind="permission" message="无权访问" />);
      expect(screen.getByText("无权访问")).toBeInTheDocument();
    });
    it("fires retry callback", () => {
      const onRetry = vi.fn();
      render(<ErrorState kind="generic" onRetry={onRetry} />);
      fireEvent.click(screen.getByRole("button", { name: /重试/ }));
      expect(onRetry).toHaveBeenCalledTimes(1);
    });
  });

  describe("pagination", () => {
    const onPage = vi.fn();
    it("disables previous on the first page and enables next", () => {
      render(
        <Pagination offset={0} limit={10} count={10} total={30} nextOffset={10} onPage={onPage} />,
      );
      expect(screen.getByRole("button", { name: /上一页/ })).toBeDisabled();
      expect(screen.getByRole("button", { name: /下一页/ })).toBeEnabled();
    });
    it("reports total when known", () => {
      render(
        <Pagination offset={10} limit={10} count={10} total={30} nextOffset={20} onPage={onPage} />,
      );
      expect(screen.getByText(/共 30 条/)).toBeInTheDocument();
    });
  });

  describe("json viewer", () => {
    it("expands and collapses the contract body", () => {
      render(<JsonViewer value={{ a: 1 }} label="evidence" />);
      expect(screen.queryByText(/"a": 1/)).not.toBeInTheDocument();
      fireEvent.click(screen.getByText("evidence"));
      expect(screen.getByText(/"a": 1/)).toBeInTheDocument();
      fireEvent.click(screen.getByText("收起"));
      expect(screen.queryByText(/"a": 1/)).not.toBeInTheDocument();
    });
  });
});

import { Link, useSearchParams } from "react-router-dom";
import { useState } from "react";

import {
  useAddMember,
  useCreateProject,
  useLinkInvestigation,
  useProject,
  useProjectInvestigations,
  useProjectMembers,
  useProjects,
  useRemoveMember,
  useUnlinkInvestigation,
  useUpdateProject,
} from "../hooks/use-projects";
import { useAuthStore } from "../stores/auth-store";
import { hasRole } from "../utils/roles";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import type { Project, ProjectRole } from "../types/projects";
import { cn } from "../utils/cn";

const STATUS_TONE: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700",
  archived: "bg-slate-100 text-slate-500",
};

const ROLE_TONE: Record<string, string> = {
  admin: "bg-brand-50 text-brand-700",
  operator: "bg-sky-50 text-sky-700",
  analyst: "bg-sky-50 text-sky-700",
  viewer: "bg-slate-100 text-slate-600",
};

/**
 * Project workspace (B18 UI over the B12 contract). Creation, membership and
 * archive are real server mutations, each audited server-side; viewers get
 * read-only rendering.
 */
export function ProjectsPage() {
  const role = useAuthStore((state) => state.role);
  const canManage = hasRole("analyst", role);
  const [searchParams] = useSearchParams();
  const selectedId = Number(searchParams.get("selected") ?? "0") || 0;
  const [showCreate, setShowCreate] = useState(false);

  const projects = useProjects();

  return (
    <div className="space-y-4">
      <PageHeader
        title="项目管理"
        description="多项目业务隔离：成员、调查引用与权限均按项目隔离，全部写操作进入持久化审计。"
        actions={
          canManage ? (
            <Button onClick={() => setShowCreate((previous) => !previous)}>
              {showCreate ? "收起" : "新建项目"}
            </Button>
          ) : undefined
        }
      />

      {showCreate && canManage && <CreateProjectForm onDone={() => setShowCreate(false)} />}

      {projects.isPending ? (
        <PageHeader title="项目列表" description="加载中…" />
      ) : projects.isError ? (
        <ErrorState
          title="项目列表加载失败"
          message={projects.error instanceof Error ? projects.error.message : "未知错误"}
          code={(projects.error as { code?: string }).code}
          onRetry={() => void projects.refetch()}
          retrying={projects.isFetching}
        />
      ) : projects.data && projects.data.items.length === 0 ? (
        <Card title="还没有项目">
          <p className="text-xs text-slate-500">
            {canManage
              ? "点击「新建项目」创建第一个项目；创建者自动成为项目管理员。"
              : "您尚未加入任何项目。请联系项目管理员添加成员。"}
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {(projects.data?.items ?? []).map((project) => (
            <ProjectCard key={project.project_id} project={project} selected={project.project_id === selectedId} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project, selected }: { project: Project; selected: boolean }) {
  const role = useAuthStore((state) => state.role);
  const canManage = hasRole("analyst", role);
  const [expanded, setExpanded] = useState(selected);
  const detail = useProject(expanded ? project.project_id : 0);
  const investigations = useProjectInvestigations(expanded ? project.project_id : 0);
  const members = useProjectMembers(expanded ? project.project_id : 0);
  const archive = useUpdateProject(project.project_id);
  const addMember = useAddMember(project.project_id);
  const removeMember = useRemoveMember(project.project_id);
  const link = useLinkInvestigation(project.project_id);
  const unlink = useUnlinkInvestigation(project.project_id);
  const [newMemberName, setNewMemberName] = useState("");
  const [newMemberRole, setNewMemberRole] = useState<ProjectRole>("viewer");
  const [linkRequestId, setLinkRequestId] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const isProjectAdmin = detail.data?.membership_role === "admin";

  const run = async (action: () => Promise<unknown>) => {
    setActionError(null);
    try {
      await action();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "操作失败");
    }
  };

  return (
    <Card
      title={project.name}
      description={`${project.status} · 创建者 ${project.created_by ?? "—"} · ${project.investigation_count} 项调查引用`}
      action={
        <div className="flex items-center gap-2">
          <Badge variant="neutral" className={cn("text-[10px]", STATUS_TONE[project.status] ?? "")}>
            {project.status}
          </Badge>
          <button type="button" onClick={() => setExpanded((previous) => !previous)} className="text-xs text-brand-700 hover:underline">
            {expanded ? "收起" : "管理"}
          </button>
        </div>
      }
    >
      {project.description && <p className="mb-2 text-xs text-slate-600">{project.description}</p>}

      {expanded && (
        <div className="space-y-3 text-xs">
          {detail.data && (
            <p className="text-slate-500">
              您的项目内角色：
              <Badge variant="neutral" className={cn("mx-1", ROLE_TONE[detail.data.membership_role] ?? "")}>
                {detail.data.membership_role}
              </Badge>
            </p>
          )}
          {actionError && (
            <p className="rounded-md border border-red-200 bg-red-50 p-2 text-red-700">{actionError}</p>
          )}

          <section>
            <h4 className="mb-1 font-medium text-slate-700">调查引用</h4>
            {(investigations.data?.items ?? []).length === 0 ? (
              <p className="text-slate-400">尚无关联调查。</p>
            ) : (
              <ul className="space-y-1">
                {(investigations.data?.items ?? []).map((reference) => (
                  <li key={reference.agentguard_request_id} className="flex items-center justify-between gap-2">
                    <Link
                      to={`/investigations/${encodeURIComponent(reference.agentguard_request_id)}/workspace`}
                      className="font-mono text-brand-700 hover:underline"
                    >
                      {reference.agentguard_request_id}
                    </Link>
                    <span className="flex items-center gap-2">
                      <Badge variant="neutral" className="text-[10px]">{reference.verification}</Badge>
                      {canManage && project.status === "active" && (
                        <button
                          type="button"
                          onClick={() => void run(() => unlink.mutateAsync(reference.agentguard_request_id))}
                          className="text-slate-400 hover:text-red-600"
                        >
                          解除
                        </button>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {canManage && project.status === "active" && (
              <div className="mt-2 flex gap-1.5">
                <input
                  value={linkRequestId}
                  onChange={(event) => setLinkRequestId(event.target.value)}
                  placeholder="AgentGuard request_id"
                  className="w-48 rounded-md border border-surface-border px-2 py-1 font-mono text-[11px]"
                />
                <Button
                  variant="secondary"
                  disabled={!linkRequestId.trim() || link.isPending}
                  onClick={() =>
                    void run(async () => {
                      await link.mutateAsync({ requestId: linkRequestId.trim(), displayName: null, notes: null });
                      setLinkRequestId("");
                    })
                  }
                >
                  关联
                </Button>
              </div>
            )}
          </section>

          <section>
            <h4 className="mb-1 font-medium text-slate-700">成员</h4>
            <ul className="space-y-1">
              {(members.data?.items ?? []).map((member) => (
                <li key={member.username} className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2">
                    <span className="text-slate-700">{member.username}</span>
                    <Badge variant="neutral" className={cn("text-[10px]", ROLE_TONE[member.role] ?? "")}>
                      {member.role}
                    </Badge>
                  </span>
                  {isProjectAdmin && project.status === "active" && (
                    <button
                      type="button"
                      onClick={() => void run(() => removeMember.mutateAsync(member.username))}
                      className="text-slate-400 hover:text-red-600"
                    >
                      移除
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {isProjectAdmin && project.status === "active" && (
              <div className="mt-2 flex gap-1.5">
                <input
                  value={newMemberName}
                  onChange={(event) => setNewMemberName(event.target.value)}
                  placeholder="用户名"
                  className="w-32 rounded-md border border-surface-border px-2 py-1 text-[11px]"
                />
                <select
                  value={newMemberRole}
                  onChange={(event) => setNewMemberRole(event.target.value as ProjectRole)}
                  className="rounded-md border border-surface-border px-1 py-1 text-[11px]"
                >
                  <option value="viewer">viewer</option>
                  <option value="analyst">analyst</option>
                  <option value="operator">operator</option>
                  <option value="admin">admin</option>
                </select>
                <Button
                  variant="secondary"
                  disabled={!newMemberName.trim() || addMember.isPending}
                  onClick={() =>
                    void run(async () => {
                      await addMember.mutateAsync({ username: newMemberName.trim(), role: newMemberRole });
                      setNewMemberName("");
                    })
                  }
                >
                  添加
                </Button>
              </div>
            )}
          </section>

          {canManage && (
            <div className="flex gap-2 border-t border-surface-border pt-2">
              {project.status === "active" ? (
                isProjectAdmin && (
                  <Button
                    variant="secondary"
                    disabled={archive.isPending}
                    onClick={() => void run(() => archive.mutateAsync({ status: "archived" }))}
                  >
                    归档项目
                  </Button>
                )
              ) : (
                isProjectAdmin && (
                  <Button
                    variant="secondary"
                    disabled={archive.isPending}
                    onClick={() => void run(() => archive.mutateAsync({ status: "active" }))}
                  >
                    恢复活跃
                  </Button>
                )
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function CreateProjectForm({ onDone }: { onDone: () => void }) {
  const create = useCreateProject();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  return (
    <Card title="新建项目" description="创建者自动获得该项目 admin 角色">
      <div className="space-y-2">
        {error && <p className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">{error}</p>}
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="项目名称（唯一）"
          className="w-72 rounded-md border border-surface-border px-2 py-1.5 text-sm"
        />
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="项目描述（可选）"
          rows={2}
          className="w-96 rounded-md border border-surface-border px-2 py-1.5 text-sm"
        />
        <div className="flex gap-2">
          <Button
            disabled={!name.trim() || create.isPending}
            onClick={() =>
              void (async () => {
                setError(null);
                try {
                  await create.mutateAsync({ name: name.trim(), description: description.trim() || null });
                  onDone();
                } catch (mutationError) {
                  setError(mutationError instanceof Error ? mutationError.message : "创建失败");
                }
              })()
            }
          >
            创建
          </Button>
          <Button variant="secondary" onClick={onDone}>取消</Button>
        </div>
      </div>
    </Card>
  );
}

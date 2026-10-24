import { useQuery } from "@tanstack/react-query";

import { useAuthStore } from "../stores/auth-store";
import { apiGet } from "../services/api";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { PageHeader } from "../components/shared/page-header";
import type { MetaInfo } from "../types/dashboard";

interface SystemSettingsData {
  meta: MetaInfo;
  auth_enabled: boolean;
  current_user?: { username: string; role: string; display_name: string } | null;
  roles: { name: string; description: string }[];
}

function fetchSettings(signal?: AbortSignal): Promise<SystemSettingsData> {
  return apiGet<SystemSettingsData>("/system/settings", signal);
}

export function SettingsPage() {
  const role = useAuthStore((state) => state.role);
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["settings"],
    queryFn: ({ signal }) => fetchSettings(signal),
  });

  return (
    <div className="space-y-4">
      <PageHeader title="系统设置" description="数据模式、角色权限与安全边界。应用层 Operator 不自动映射为 AgentGuard 高权限操作员。" />

      {isLoading && <p className="text-sm text-slate-400">正在加载设置…</p>}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-xs text-red-700">
          设置不可用：{error instanceof Error ? error.message : "未知错误"}
          <button
            type="button"
            onClick={() => void refetch()}
            className="ml-3 underline disabled:opacity-50"
            disabled={isFetching}
          >
            重试
          </button>
        </div>
      )}

      {data && (
        <>
          <Card title="当前环境">
            <div className="flex flex-wrap gap-4 text-xs">
              <div className="flex items-center gap-2">
                数据模式：<Badge variant={data.meta.data_mode === "live" ? "ok" : "neutral"}>{data.meta.data_mode}</Badge>
              </div>
              <div className="flex items-center gap-2">
                应用认证：
                <Badge variant={data.auth_enabled ? "ok" : "neutral"}>{data.auth_enabled ? "AUTH_ENABLED" : "本地开发模式"}</Badge>
              </div>
              <div className="flex items-center gap-2">
                当前角色：
                <span className="font-mono font-medium text-slate-800">{role ?? "未登录"}</span>
              </div>
            </div>
            {data.current_user && (
              <p className="mt-2 text-xs text-slate-500">
                {data.current_user.display_name}（{data.current_user.username}）
              </p>
            )}
          </Card>

          <Card title="角色与权限">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-surface-border text-left text-slate-500">
                    <th className="py-2 pr-4 font-medium">角色</th>
                    <th className="py-2 font-medium">说明</th>
                  </tr>
                </thead>
                <tbody>
                  {data.roles.map((entry) => (
                    <tr key={entry.name} className="border-b border-surface-border last:border-0">
                      <td className="py-2 pr-4 font-mono text-slate-800">{entry.name}</td>
                      <td className="py-2 text-slate-600">{entry.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px] text-slate-400">
              最小权限模型。AgentGuard 的真实授权仍通过其自身校验；应用层角色不授予 AgentGuard 高权限操作员身份。
            </p>
          </Card>

          <Card title="安全边界">
            <ul className="list-inside list-disc space-y-1 text-xs text-slate-600">
              <li>AgentGuard Token 仅存在于服务端，浏览器只持有应用层会话 Cookie（HttpOnly、SameSite=Lax，HTTPS 下可开启 Secure）。</li>
              <li>上游地址固定于服务端配置，前端无法指定任意上游（防 SSRF）。</li>
              <li>修改操作经 CSRF 双提交校验与服务端角色授权。</li>
              <li>业务操作审计：调查创建与防御预览记录到 app_audit_events（Operator+ 可查）。</li>
              <li>演示数据不进入 AgentGuard 经验奖励库，不得用于真实因果实验统计。</li>
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}

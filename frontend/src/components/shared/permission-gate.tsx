import { ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import { useAuthStore } from "../../stores/auth-store";
import { hasRole, type Role } from "../../utils/roles";

/**
 * Role gate. When the current session does not have the required role the
 * children are replaced with an explicit permission-denied state.
 */
export function PermissionGate({
  required,
  children,
}: {
  required: Role;
  children: ReactNode;
}) {
  const role = useAuthStore((state) => state.role);
  if (hasRole(required, role)) return <>{children}</>;
  return (
    <div className="flex flex-col items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-amber-800">
        <ShieldAlert aria-hidden className="h-4 w-4" />
        权限不足
      </div>
      <p className="text-xs text-amber-700">
        当前角色 {role ?? "未登录"} 无权执行该操作（需要 {required} 及以上）。
      </p>
    </div>
  );
}

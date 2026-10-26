import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useSessionBootstrap } from "../../hooks/use-session-bootstrap";
import { login, logout } from "../../services/auth";
import { useAuthStore } from "../../stores/auth-store";
import { Button } from "../ui/button";

export function SessionControl() {
  const status = useSessionBootstrap();
  const queryClient = useQueryClient();
  const role = useAuthStore((state) => state.role);
  const username = useAuthStore((state) => state.username);
  const authEnabled = useAuthStore((state) => state.authEnabled);
  const setSession = useAuthStore((state) => state.setSession);
  const [usernameInput, setUsernameInput] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setWorking(true);
    try {
      const me = await login(usernameInput.trim(), password);
      if (!me.authenticated || !me.user) {
        setError(me.message ?? "登录失败，请检查账号信息。");
        return;
      }
      queryClient.clear();
      setSession({
        role: me.user.role,
        username: me.user.username,
        displayName: me.user.display_name,
        authEnabled: me.auth_enabled,
      });
      setPassword("");
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "登录失败，请重试。");
    } finally {
      setWorking(false);
    }
  };

  const handleLogout = async () => {
    setError("");
    setWorking(true);
    try {
      const me = await logout();
      queryClient.clear();
      setSession({
        role: me.user?.role ?? null,
        username: me.user?.username ?? null,
        displayName: me.user?.display_name ?? null,
        authEnabled: me.auth_enabled,
      });
    } catch (logoutError) {
      setError(logoutError instanceof Error ? logoutError.message : "退出登录失败，请重试。");
    } finally {
      setWorking(false);
    }
  };

  if (status === "loading") {
    return <span className="text-xs text-slate-400">正在读取登录状态…</span>;
  }

  if (authEnabled && !username) {
    return (
      <div className="flex flex-col items-end gap-1">
        <form aria-label="登录表单" onSubmit={(event) => void handleLogin(event)} className="flex items-center gap-1.5">
          <label className="sr-only" htmlFor="session-username">用户名</label>
          <input
            id="session-username"
            autoComplete="username"
            required
            value={usernameInput}
            onChange={(event) => setUsernameInput(event.target.value)}
            placeholder="用户名"
            className="w-28 rounded border border-surface-border px-2 py-1 text-xs"
          />
          <label className="sr-only" htmlFor="session-password">密码</label>
          <input
            id="session-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="密码"
            className="w-28 rounded border border-surface-border px-2 py-1 text-xs"
          />
          <Button type="submit" disabled={working} className="px-2 py-1 text-xs">
            {working ? "处理中…" : "登录"}
          </Button>
        </form>
        {error && <p role="alert" className="max-w-64 text-right text-[11px] text-red-700">{error}</p>}
      </div>
    );
  }

  if (!authEnabled) {
    return <span className="text-xs text-slate-500">{role ?? "Viewer"}{username ? ` · ${username}` : ""}</span>;
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500">{role ?? "Viewer"} · {username}</span>
      <Button variant="secondary" disabled={working} onClick={() => void handleLogout()} className="px-2 py-1 text-xs">
        {working ? "处理中…" : "退出登录"}
      </Button>
      {error && <span role="alert" className="text-[11px] text-red-700">{error}</span>}
    </div>
  );
}

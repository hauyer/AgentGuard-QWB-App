import { useEffect } from "react";

import { fetchMe } from "../services/auth";
import { useAuthStore } from "../stores/auth-store";

/** On app start, hydrate the UI session from the BFF (cookie-based, token never leaves the server). */
export function useSessionBootstrap() {
  const status = useAuthStore((state) => state.status);
  useEffect(() => {
    if (status === "ready") return;
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        useAuthStore.getState().setSession({
          role: me.user?.role ?? null,
          username: me.user?.username ?? null,
          displayName: me.user?.display_name ?? null,
          authEnabled: me.auth_enabled,
        });
      })
      .catch(() => {
        if (cancelled) return;
        useAuthStore.getState().clearSession();
      });
    return () => {
      cancelled = true;
    };
  }, [status]);
  return status;
}

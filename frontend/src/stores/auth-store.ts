import { create } from "zustand";

export type Role = "viewer" | "analyst" | "operator" | "admin";

interface AuthState {
  role: Role | null;
  username: string | null;
  displayName: string | null;
  authEnabled: boolean;
  status: "loading" | "ready";
  setSession: (session: {
    role: Role | null;
    username?: string | null;
    displayName?: string | null;
    authEnabled: boolean;
  }) => void;
  clearSession: () => void;
}

/**
 * Lightweight session store: only what the UI needs (role + identity).
 * Server-side session state stays on the BFF; the browser never holds tokens.
 */
export const useAuthStore = create<AuthState>()((set) => ({
  role: null,
  username: null,
  displayName: null,
  authEnabled: false,
  status: "loading",
  setSession: (session) =>
    set({
      role: session.role,
      username: session.username ?? null,
      displayName: session.displayName ?? null,
      authEnabled: session.authEnabled,
      status: "ready",
    }),
  clearSession: () =>
    set({ role: null, username: null, displayName: null, authEnabled: false, status: "ready" }),
}));

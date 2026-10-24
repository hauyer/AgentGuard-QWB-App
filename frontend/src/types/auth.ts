export type Role = "viewer" | "analyst" | "operator" | "admin";

export interface AuthUser {
  username: string;
  display_name: string;
  role: Role;
}

export interface AuthMe {
  authenticated: boolean;
  auth_enabled: boolean;
  user: AuthUser | null;
  message?: string | null;
}

export type Role = "viewer" | "analyst" | "operator" | "admin";

export const ROLE_ORDER: Role[] = ["viewer", "analyst", "operator", "admin"];

export function hasRole(required: Role, current: Role | null | undefined): boolean {
  if (!current) return false;
  return ROLE_ORDER.indexOf(current) >= ROLE_ORDER.indexOf(required);
}

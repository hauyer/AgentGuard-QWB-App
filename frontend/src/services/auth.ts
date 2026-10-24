import type { AuthMe } from "../types/auth";
import { apiGet, apiPost } from "./api";

export function fetchMe(signal?: AbortSignal): Promise<AuthMe> {
  return apiGet<AuthMe>("/auth/me", signal);
}

export function login(username: string, password: string): Promise<AuthMe> {
  return apiPost<AuthMe>("/auth/login", { username, password });
}

export function logout(): Promise<AuthMe> {
  return apiPost<AuthMe>("/auth/logout");
}

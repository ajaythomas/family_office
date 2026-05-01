import type { components } from "../types/api";

type TokenResponse = components["schemas"]["TokenResponse"];
type UserRead = components["schemas"]["UserRead"];

const API = import.meta.env.VITE_API_URL;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function login(idToken: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
}

export function getMe(token: string): Promise<UserRead> {
  return request<UserRead>("/users/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

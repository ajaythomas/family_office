import type { components } from "../types/api";

type TokenResponse = components["schemas"]["TokenResponse"];
type UserRead = components["schemas"]["UserRead"];
type PortfolioRead = components["schemas"]["PortfolioRead"];
type PortfolioReadEnriched = components["schemas"]["PortfolioReadEnriched"];
type HoldingRead = components["schemas"]["HoldingRead"];
type HoldingCreate = components["schemas"]["HoldingCreate"];
type HoldingSell = components["schemas"]["HoldingSell"];

const API = import.meta.env.VITE_API_URL;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function auth(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export function login(idToken: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
}

export function getMe(token: string): Promise<UserRead> {
  return request<UserRead>("/users/me", { headers: auth(token) });
}

export function listPortfolios(token: string): Promise<PortfolioRead[]> {
  return request<PortfolioRead[]>("/portfolios", { headers: auth(token) });
}

export function getPortfolio(token: string, portfolioId: string): Promise<PortfolioReadEnriched> {
  return request<PortfolioReadEnriched>(`/portfolios/${portfolioId}`, { headers: auth(token) });
}

export function addHolding(
  token: string,
  portfolioId: string,
  body: HoldingCreate,
): Promise<HoldingRead> {
  return request<HoldingRead>(`/portfolios/${portfolioId}/holdings`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth(token) },
    body: JSON.stringify(body),
  });
}

export function deleteHolding(token: string, portfolioId: string, holdingId: string): Promise<void> {
  return request<void>(`/portfolios/${portfolioId}/holdings/${holdingId}`, {
    method: "DELETE",
    headers: auth(token),
  });
}

export function sellHolding(
  token: string,
  portfolioId: string,
  holdingId: string,
  body: HoldingSell,
): Promise<HoldingRead> {
  return request<HoldingRead>(`/portfolios/${portfolioId}/holdings/${holdingId}/sell`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...auth(token) },
    body: JSON.stringify(body),
  });
}

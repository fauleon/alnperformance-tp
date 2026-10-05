"use client";

/** Browser client for the API, proxied by this Next.js server under /api (same origin, cookie session). */

export class ApiError extends Error {
  status: number;
  problems: string[];
  needsReconnect: boolean;
  constructor(status: number, message: string, problems: string[] = [], needsReconnect = false) {
    super(message);
    this.status = status;
    this.problems = problems;
    this.needsReconnect = needsReconnect;
  }
}

function readError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(status, detail);
  if (Array.isArray(detail)) {
    return new ApiError(status, "Dados inválidos.", detail.map((d: { loc?: string[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg ?? ""}`));
  }
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; problems?: Array<string | { field: string; message: string }>; violations?: string[]; needs_reconnect?: boolean };
    const problems = [...(d.problems ?? []).map(p => typeof p === "string" ? p : `${p.field}: ${p.message}`), ...(d.violations ?? [])];
    return new ApiError(status, d.message ?? "Não foi possível concluir.", problems, Boolean(d.needs_reconnect));
  }
  if (status === 429) return new ApiError(status, "Muitas tentativas. Aguarde um pouco.");
  return new ApiError(status, status >= 500 ? "O servidor não respondeu como esperado. Tente de novo." : "Não foi possível concluir.");
}

export async function api<T = unknown>(path: string, init: { method?: string; body?: unknown; headers?: Record<string, string> } = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Requested-With": "alnia", Accept: "application/json", ...init.headers };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: init.method ?? "GET", headers, credentials: "same-origin", cache: "no-store",
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError(0, "Sem conexão com o servidor. Verifique a internet e tente de novo.");
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = readError(response.status, body);
    if (response.status === 401 && typeof window !== "undefined" && window.location.pathname.startsWith("/app")) {
      window.location.assign(`/entrar?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
    }
    throw error;
  }
  return body as T;
}

/** SWR fetcher for keys shaped as [path, workspaceId]. The workspace is part of the key, so caches never mix. */
export const workspaceFetcher = <T,>([path, workspace]: [string, string | null]) =>
  api<T>(path, { headers: workspace ? { "X-Workspace-Id": workspace } : {} });

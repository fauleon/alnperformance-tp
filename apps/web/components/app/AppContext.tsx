"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import useSWR, { type SWRConfiguration } from "swr";
import { api, workspaceFetcher } from "@/lib/api";
import type { AdAccount, Me, Role, SystemInfo } from "@/lib/types";

type Toast = { kind: "ok" | "error"; text: string } | null;

type AppState = {
  me: Me | undefined;
  workspaceId: string | null;
  setWorkspaceId: (id: string) => void;
  role: Role;
  canEdit: boolean;
  isOwner: boolean;
  system: SystemInfo | undefined;
  accounts: AdAccount[];
  accountsLoading: boolean;
  account: AdAccount | null;
  setAccountId: (id: string) => void;
  days: number;
  setDays: (days: number) => void;
  call: <T = unknown>(path: string, init?: { method?: string; body?: unknown; headers?: Record<string, string> }) => Promise<T>;
  toast: Toast;
  notify: (kind: "ok" | "error", text: string) => void;
  reloadAccounts: () => void;
};

const Ctx = createContext<AppState | null>(null);

function stored(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function store(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* private mode: selection is just not remembered */ }
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const { data: me } = useSWR<Me>(["/v1/auth/me", null], workspaceFetcher);
  const [workspaceId, setWs] = useState<string | null>(null);
  const [accountId, setAcc] = useState<string | null>(null);
  const [days, setDaysState] = useState(30);
  const [toast, setToast] = useState<Toast>(null);

  useEffect(() => {
    if (!me || workspaceId) return;
    const saved = stored("alnia.workspace");
    setWs(me.workspaces.find(w => w.id === saved)?.id ?? me.workspaces[0]?.id ?? null);
    const savedDays = Number(stored("alnia.days"));
    if ([7, 14, 30, 90].includes(savedDays)) setDaysState(savedDays);
  }, [me, workspaceId]);

  const { data: system } = useSWR<SystemInfo>(workspaceId ? ["/v1/system", workspaceId] : null, workspaceFetcher);
  const { data: accountList, isLoading: accountsLoading, mutate: reloadAccountList } = useSWR<AdAccount[]>(workspaceId ? ["/v1/accounts", workspaceId] : null, workspaceFetcher);
  const accounts = useMemo(() => accountList ?? [], [accountList]);

  useEffect(() => {
    if (!workspaceId || !accountList) return;
    const saved = stored(`alnia.account.${workspaceId}`);
    setAcc(current => accountList.find(a => a.id === current)?.id ?? accountList.find(a => a.id === saved)?.id ?? accountList[0]?.id ?? null);
  }, [workspaceId, accountList]);

  const role: Role = me?.workspaces.find(w => w.id === workspaceId)?.role ?? "viewer";

  const call = useCallback(<T,>(path: string, init: { method?: string; body?: unknown; headers?: Record<string, string> } = {}) =>
    api<T>(path, { ...init, headers: { ...(workspaceId ? { "X-Workspace-Id": workspaceId } : {}), ...init.headers } }), [workspaceId]);

  const notify = useCallback((kind: "ok" | "error", text: string) => {
    setToast({ kind, text });
    window.setTimeout(() => setToast(current => (current?.text === text ? null : current)), 5200);
  }, []);

  const value: AppState = {
    me, workspaceId, role, canEdit: role === "owner" || role === "admin", isOwner: role === "owner", system,
    setWorkspaceId: id => { store("alnia.workspace", id); setAcc(null); setWs(id); },
    accounts, accountsLoading, account: accounts.find(a => a.id === accountId) ?? null,
    setAccountId: id => { if (workspaceId) store(`alnia.account.${workspaceId}`, id); setAcc(id); },
    days, setDays: d => { store("alnia.days", String(d)); setDaysState(d); },
    call, toast, notify, reloadAccounts: () => { void reloadAccountList(); },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const value = useContext(Ctx);
  if (!value) throw new Error("useApp fora do AppProvider");
  return value;
}

/** Workspace-scoped SWR. Pass null to skip. */
export function useApi<T>(path: string | null, config?: SWRConfiguration<T>) {
  const { workspaceId } = useApp();
  return useSWR<T>(path && workspaceId ? [path, workspaceId] : null, workspaceFetcher, config);
}

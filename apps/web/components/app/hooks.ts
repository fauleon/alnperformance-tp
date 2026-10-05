"use client";

import { useState } from "react";
import { useApp, useApi } from "@/components/app/AppContext";
import { ApiError } from "@/lib/api";
import type { AuditReport, PlanKind, PlanSummary, Snapshot } from "@/lib/types";

export function useSnapshot() {
  const { account, days } = useApp();
  return useApi<Snapshot>(account ? `/v1/accounts/${account.id}/snapshot?days=${days}` : null, { revalidateOnFocus: false });
}

export function useAuditReport() {
  const { account, days } = useApp();
  return useApi<AuditReport>(account ? `/v1/accounts/${account.id}/audit?days=${days}` : null, { revalidateOnFocus: false });
}

/** Refreshes the account snapshot from the platform (bypasses the cache). */
export function useRefresh(onDone: () => void) {
  const { account, days, call, notify } = useApp();
  const [busy, setBusy] = useState(false);
  async function refresh() {
    if (!account) return;
    setBusy(true);
    try {
      await call(`/v1/accounts/${account.id}/snapshot?days=${days}&refresh=true`);
      onDone();
      notify("ok", "Dados atualizados da plataforma.");
    } catch (error) {
      notify("error", error instanceof ApiError ? error.message : "Não foi possível atualizar.");
    } finally {
      setBusy(false);
    }
  }
  return { refresh, busy };
}

/** Creates a plan from a proposal (audit, copilot, quick action) and returns its id. */
export function useCreatePlan() {
  const { account, call, notify } = useApp();
  return async (kind: PlanKind, content: Record<string, unknown>, source: "manual" | "copilot" | "audit" | "template" = "manual") => {
    if (!account) return null;
    try {
      const plan = await call<PlanSummary>("/v1/plans", { method: "POST", body: { kind, account_id: account.id, content, source } });
      notify("ok", "Proposta criada. Revise e valide antes de aprovar.");
      return plan.id;
    } catch (error) {
      notify("error", error instanceof ApiError ? [error.message, ...error.problems.slice(0, 2)].join(" ") : "Não foi possível criar a proposta.");
      return null;
    }
  };
}

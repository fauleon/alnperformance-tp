"use client";

import Link from "next/link";
import { useState } from "react";
import { useApp, useApi } from "@/components/app/AppContext";
import { Empty, ErrorBox, Loading, PageHead, StatusBadge } from "@/components/app/ui";
import { Arrow } from "@/components/ui";
import { dateTimeBR, KIND_LABEL, STATUS_LABEL } from "@/lib/format";
import type { PlanSummary } from "@/lib/types";

const FILTERS = ["", "DRAFT", "VALIDATED", "BLOCKED", "APPROVED", "QUEUED", "EXECUTED", "FAILED", "ARCHIVED"];
const SOURCE: Record<string, string> = { manual: "Manual", copilot: "Copiloto", audit: "Auditoria", template: "Modelo", revert: "Reversão" };

export default function PlansPage() {
  const { canEdit, accounts } = useApp();
  const [status, setStatus] = useState("");
  const plans = useApi<PlanSummary[]>(`/v1/plans${status ? `?status=${status}` : ""}`);
  const accountName = (id: string | null) => accounts.find(a => a.id === id)?.name ?? "—";

  return <>
    <PageHead eyebrow="Central de decisões" title="Planos e aprovações" text="Toda mudança passa por aqui: proposta, validação, aprovação da versão exata, execução e histórico."
      actions={canEdit && <Link className="button button-primary button-sm" href="/app/planos/novo">Novo plano <Arrow/></Link>}/>
    <div className="chart-switch" role="group" aria-label="Filtrar por status">
      {FILTERS.map(f => <button key={f || "all"} type="button" aria-pressed={status === f} onClick={() => setStatus(f)}>{f ? STATUS_LABEL[f] : "Em aberto"}</button>)}
    </div>
    <div className="card">
      {plans.error ? <ErrorBox error={plans.error} onRetry={() => plans.mutate()}/> : !plans.data ? <Loading/> : plans.data.length === 0
        ? <Empty title="Nenhum plano aqui" text="Crie uma campanha, use uma correção da auditoria ou peça ao copiloto."/>
        : <div className="table-wrap" tabIndex={0}><table className="table"><thead><tr><th>Plano</th><th>Tipo</th><th>Conta</th><th>Origem</th><th>Status</th><th>Atualizado</th></tr></thead><tbody>
          {plans.data.map(p => <tr key={p.id}>
            <td><Link className="row-button" href={`/app/planos/${p.id}`}>{p.title}</Link><br/><small className="muted">v{p.version}</small></td>
            <td>{KIND_LABEL[p.kind]}</td><td>{accountName(p.account_id)}</td><td>{SOURCE[p.source] ?? p.source}</td>
            <td><StatusBadge status={p.status}/></td><td>{dateTimeBR(p.updated_at)}</td>
          </tr>)}
        </tbody></table></div>}
    </div>
  </>;
}

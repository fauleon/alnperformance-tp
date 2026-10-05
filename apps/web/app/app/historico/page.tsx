"use client";

import { useState } from "react";
import { useApi } from "@/components/app/AppContext";
import { Empty, ErrorBox, Loading, PageHead } from "@/components/app/ui";
import { dateTimeBR } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";

const ACTIONS: Record<string, string> = {
  "plan.created": "Plano criado", "plan.revised": "Nova versão do plano", "plan.validated": "Plano validado", "plan.approved": "Plano aprovado",
  "plan.execution_queued": "Execução enviada", "plan.executed": "Executado na plataforma", "plan.execution_failed": "Execução falhou",
  "connection.oauth_started": "Conexão iniciada", "connection.connected": "Conta conectada", "connection.oauth_denied": "Autorização cancelada",
  "connection.oauth_failed": "Falha na conexão", "connection.needs_reconnect": "Conexão precisa ser refeita", "connection.disconnected": "Conexão revogada",
  "account.linked": "Conta vinculada", "account.unlinked": "Conta desvinculada", "workspace.created": "Cliente criado", "workspace.updated": "Cliente atualizado",
  "invitation.created": "Convite criado", "invitation.accepted": "Convite aceito", "member.role_changed": "Papel alterado", "member.removed": "Membro removido",
  "conversion.offline_uploaded": "Conversão offline enviada", "reconcile.drift": "Divergência na reconciliação", "user.signup": "Cadastro",
};
const FILTERS = [["", "Tudo"], ["plan.", "Planos"], ["connection.", "Conexões"], ["account.", "Contas"], ["member.", "Equipe"]];

export default function History() {
  const [filter, setFilter] = useState("");
  const events = useApi<AuditEvent[]>(`/v1/audit?limit=200${filter ? `&action=${filter}` : ""}`);
  return <>
    <PageHead eyebrow="Rastreabilidade total" title="Histórico" text="Cada conexão, proposta, validação, aprovação e execução, com data, responsável e resultado. Tokens e dados pessoais nunca aparecem aqui."/>
    <div className="chart-switch" role="group" aria-label="Filtrar">{FILTERS.map(([value, label]) => <button key={label} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
    <div className="card">
      {events.error ? <ErrorBox error={events.error}/> : !events.data ? <Loading/> : events.data.length === 0 ? <Empty title="Sem eventos" text="As ações aparecem aqui assim que acontecem."/>
        : <div className="table-wrap" tabIndex={0}><table className="table"><thead><tr><th>Quando</th><th>Ação</th><th>Quem</th><th>Resultado</th><th>Detalhes</th></tr></thead><tbody>
          {events.data.map(e => <tr key={e.id}><td>{dateTimeBR(e.occurred_at)}</td><td>{ACTIONS[e.action] ?? e.action}</td><td>{e.actor}</td><td>{e.result}</td>
            <td>{e.details ? <details><summary className="muted">ver</summary><pre className="pre" tabIndex={0}>{JSON.stringify(e.details, null, 2)}</pre></details> : "—"}</td></tr>)}
        </tbody></table></div>}
    </div>
  </>;
}

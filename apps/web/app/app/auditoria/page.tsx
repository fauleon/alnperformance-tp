"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useApp } from "@/components/app/AppContext";
import { useAuditReport, useCreatePlan, useRefresh } from "@/components/app/hooks";
import { Empty, ErrorBox, Loading, NoAccount, PageHead, ScoreRing } from "@/components/app/ui";
import { dateBR, SEVERITY_LABEL } from "@/lib/format";
import type { Finding } from "@/lib/types";

const SEVERITIES = ["critical", "high", "medium", "low"] as const;

function Evidence({ evidence }: { evidence: Record<string, unknown> }) {
  const entries = Object.entries(evidence).filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && v.length === 0));
  if (!entries.length) return null;
  return <dl className="kv">{entries.map(([key, value]) => <div key={key} className="kv-row"><dt>{key.replaceAll("_", " ")}</dt><dd>{Array.isArray(value) ? value.join(", ") : String(value)}</dd></div>)}</dl>;
}

export default function AuditPage() {
  const { accounts, accountsLoading, account, canEdit } = useApp();
  const audit = useAuditReport();
  const router = useRouter();
  const createPlan = useCreatePlan();
  const { refresh, busy } = useRefresh(() => void audit.mutate());
  const [only, setOnly] = useState<string>("all");
  const [creating, setCreating] = useState<number | null>(null);

  if (!accountsLoading && accounts.length === 0) return <><PageHead eyebrow="Diagnóstico" title="Auditoria da conta"/><NoAccount/></>;

  async function fix(finding: Finding, index: number) {
    if (!finding.proposal || !account) return;
    setCreating(index);
    const id = await createPlan(account.provider === "GOOGLE_ADS" ? "GOOGLE_CHANGE" : "TIKTOK_CHANGE", finding.proposal, "audit");
    setCreating(null);
    if (id) router.push(`/app/planos/${id}`);
  }

  const data = audit.data;
  const findings = (data?.findings ?? []).map((f, i) => ({ f, i })).filter(({ f }) => only === "all" || f.severity === only);

  return <>
    <PageHead eyebrow="Diagnóstico" title="Auditoria da conta" text="Regras fixas e explicáveis, sem IA. Cada achado traz o motivo e, quando possível, a correção pronta para aprovação."
      actions={<button className="button button-ghost button-sm" type="button" onClick={refresh} disabled={busy}>{busy ? "Reauditando…" : "Reauditar com dados novos"}</button>}/>
    {audit.error ? <ErrorBox error={audit.error} onRetry={() => audit.mutate()}/> : !data ? <Loading/> : <>
      <section className="card">
        <div className="score"><ScoreRing score={data.score}/>
          <div><h2>Nota {data.score}/100</h2><p className="muted">Período de {dateBR(data.period_start)} a {dateBR(data.period_end)} · {data.findings.length} achado(s)</p>
            <div className="chart-switch" role="group" aria-label="Filtrar por gravidade">
              <button type="button" aria-pressed={only === "all"} onClick={() => setOnly("all")}>Todos ({data.findings.length})</button>
              {SEVERITIES.map(s => <button key={s} type="button" aria-pressed={only === s} onClick={() => setOnly(s)}>{SEVERITY_LABEL[s]} ({data.summary[s] ?? 0})</button>)}
            </div>
          </div>
        </div>
      </section>
      {findings.length === 0 ? <Empty title="Nenhum achado" text="As regras atuais não encontraram problemas nesta conta e período."/> : <section aria-label="Achados" className="card">
        {findings.map(({ f, i }) => <article key={`${f.rule}-${i}`} className={`finding ${f.severity}`}>
          <div className="meta"><span className={`badge ${f.severity === "critical" ? "badge-bad" : f.severity === "high" ? "badge-warn" : "badge-info"}`}>{SEVERITY_LABEL[f.severity]}</span><code>{f.rule}</code>{f.campaign_name && <span className="muted">{f.campaign_name}</span>}</div>
          <h3>{f.title}</h3>
          <p><strong>Por que importa:</strong> {f.why}</p>
          <p><strong>Como corrigir:</strong> {f.fix}</p>
          <Evidence evidence={f.evidence}/>
          {f.proposal && canEdit && <div><button className="button button-primary button-sm" type="button" disabled={creating !== null} onClick={() => fix(f, i)}>{creating === i ? "Criando…" : "Criar proposta de correção"}</button></div>}
        </article>)}
      </section>}
    </>}
  </>;
}

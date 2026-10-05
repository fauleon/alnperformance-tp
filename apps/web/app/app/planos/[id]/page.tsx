"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useApp, useApi } from "@/components/app/AppContext";
import { CampaignEditor, type SearchPlan } from "@/components/app/CampaignEditor";
import { ErrorBox, Loading, PageHead, StatusBadge, customerId, newKey } from "@/components/app/ui";
import { ApiError } from "@/lib/api";
import { dateTimeBR, KIND_LABEL, PURPOSE_LABEL } from "@/lib/format";
import type { Execution, PlanDetail, PlanSummary, Validation } from "@/lib/types";

const FLOW = ["DRAFT", "VALIDATED", "APPROVED", "QUEUED", "EXECUTED"];
const FLOW_LABEL = ["Rascunho", "Validado", "Aprovado", "Na fila", "Executado"];
const LIVE = new Set(["QUEUED", "RUNNING", "RETRYING"]);

function Stepper({ status }: { status: string }) {
  const index = status === "BLOCKED" ? 0 : status === "FAILED" ? 3 : FLOW.indexOf(status);
  return <ol className="stepper" aria-label="Etapas do plano">{FLOW_LABEL.map((label, i) =>
    <li key={label} className={i < index || status === "EXECUTED" ? "done" : i === index ? "current" : ""} aria-current={i === index ? "step" : undefined}><b>{i + 1}</b>{label}</li>)}</ol>;
}

function ValidationBox({ validation }: { validation: Validation }) {
  return <div className={`alert ${validation.allowed ? "alert-ok" : "alert-error"}`}>
    <strong>{validation.allowed ? "Validado: pronto para aprovação." : "Bloqueado: corrija os pontos abaixo."}</strong>
    <span className="muted">Versão {validation.plan_version} · {dateTimeBR(validation.validated_at)} · validação na plataforma: {{ ok: "aceita", rejected: "recusada", unavailable: "indisponível", skipped: "não executada" }[validation.remote_status]}</span>
    {validation.violations.length > 0 && <ul>{validation.violations.map(v => <li key={v}>{v}</li>)}</ul>}
    {validation.remote_errors.length > 0 && <><b>Resposta da plataforma:</b><ul>{validation.remote_errors.map(v => <li key={v}>{v}</li>)}</ul></>}
    {validation.warnings.length > 0 && <><b className="text-warn">Atenção (não bloqueia):</b><ul>{validation.warnings.map(v => <li key={v}>{v}</li>)}</ul></>}
  </div>;
}

function ExecutionRow({ execution, onRevert, canEdit }: { execution: Execution; onRevert: (id: string) => void; canEdit: boolean }) {
  const result = execution.result ?? {};
  const snippets = (result.tag_snippets as { type: string; page_format: string; global_site_tag: string; event_snippet: string }[] | undefined) ?? [];
  return <div className="card">
    <div className="card-head"><h2>Execução <StatusBadge status={execution.status}/></h2><small>{dateTimeBR(execution.created_at)}{execution.finished_at ? ` → ${dateTimeBR(execution.finished_at)}` : ""}</small></div>
    {execution.error && <div className="alert alert-error"><strong>{execution.error}</strong></div>}
    {Object.keys(result).length > 0 && <dl className="kv">
      {"status" in result && <div className="kv-row"><dt>Resultado</dt><dd>{String(result.status) === "CREATED_PAUSED" ? "Criada pausada" : String(result.status) === "ALREADY_EXISTS" ? "Já existia (nada duplicado)" : "Aplicado"}</dd></div>}
      {"campaign" in result && <div className="kv-row"><dt>Campanha</dt><dd><code className="code-inline">{String(result.campaign)}</code></dd></div>}
      {"campaign_id" in result && <div className="kv-row"><dt>Campanha</dt><dd><code className="code-inline">{String(result.campaign_id)}</code></dd></div>}
    </dl>}
    {snippets.map(s => <details key={`${s.type}-${s.page_format}`}><summary>Código da tag ({s.page_format.toLowerCase()})</summary><p className="muted">Instale a tag global em todas as páginas e o snippet de evento na página de confirmação.</p><pre className="pre" tabIndex={0}>{s.global_site_tag}{"\n\n"}{s.event_snippet}</pre></details>)}
    {execution.status === "SUCCEEDED" && canEdit && <div className="form-actions"><button className="button button-ghost button-sm" type="button" onClick={() => onRevert(execution.id)}>Reverter (gera proposta inversa)</button></div>}
  </div>;
}

export default function PlanPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { call, canEdit, system, notify } = useApp();
  const plan = useApi<PlanDetail>(`/v1/plans/${id}`, {
    refreshInterval: data => (data && (data.status === "QUEUED" || data.executions.some(e => LIVE.has(e.status))) ? 2500 : 0),
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [funds, setFunds] = useState(false);
  const [editing, setEditing] = useState(false);
  const [json, setJson] = useState("");
  const latestApproval = plan.data?.approvals.find(a => !a.consumed && a.version === plan.data?.version);
  // One key per approval: a double click or a retry after a timeout never executes twice.
  const executeKey = useMemo(() => (latestApproval ? `${latestApproval.id}-${newKey()}` : ""), [latestApproval]);

  async function act(name: string, run: () => Promise<unknown>, success: string) {
    setBusy(name);
    setError(null);
    try {
      await run();
      notify("ok", success);
      await plan.mutate();
    } catch (failure) {
      setError(failure instanceof ApiError ? failure : new ApiError(0, "Não foi possível concluir."));
    } finally {
      setBusy(null);
    }
  }

  if (plan.error) return <ErrorBox error={plan.error} onRetry={() => plan.mutate()}/>;
  if (!plan.data) return <Loading/>;
  const p = plan.data;
  const locked = p.status === "QUEUED" || p.status === "EXECUTED" || p.status === "ARCHIVED";
  const mutationsOn = system ? (p.provider === "GOOGLE_ADS" ? system.google_mutations : system.tiktok_mutations) : false;
  const validationCurrent = p.validation && p.validation.plan_version === p.version;

  const save = (content: unknown) => act("save", async () => { await call(`/v1/plans/${p.id}`, { method: "PUT", body: { content } }); setEditing(false); }, "Nova versão salva. Valide de novo.");
  const revert = (executionId: string) => act("revert", async () => {
    const created = await call<PlanSummary>(`/v1/executions/${executionId}/revert`, { method: "POST" });
    router.push(`/app/planos/${created.id}`);
  }, "Proposta de reversão criada.");

  return <>
    <PageHead eyebrow={KIND_LABEL[p.kind]} title={p.title}
      text={<>{p.account ? `${p.account.name} (${customerId(p.account.external_id)})` : "Conta removida"} · versão {p.version} · <StatusBadge status={p.status}/> · {PURPOSE_LABEL[p.purpose] ?? p.purpose}</>}
      actions={<>{canEdit && !locked && <button className="button button-ghost button-sm" type="button" onClick={() => act("archive", () => call(`/v1/plans/${p.id}/archive`, { method: "POST" }), "Plano arquivado.")}>Arquivar</button>}<Link className="button button-ghost button-sm" href="/app/planos">Voltar</Link></>}/>
    <Stepper status={p.status}/>
    {error && <div className="alert alert-error" role="alert"><strong>{error.message}</strong>{error.problems.length > 0 && <ul>{error.problems.map(x => <li key={x}>{x}</li>)}</ul>}</div>}
    {p.reverts_execution_id && <div className="alert alert-warn"><strong>Esta proposta desfaz uma execução anterior.</strong></div>}

    <div className="grid-main">
      <div>
        <section className="card">
          <div className="card-head"><h2>O que muda</h2><small>antes → depois</small></div>
          <div className="table-wrap" tabIndex={0}><table className="table diff-table"><thead><tr><th>Item</th><th>Antes</th><th>Depois</th></tr></thead>
            <tbody>{p.changes.map((c, i) => <tr key={i}><td>{c.label}</td><td>{c.before}</td><td>{c.after}</td></tr>)}</tbody></table></div>
        </section>
        {p.last_revision_diff.length > 0 && <section className="card"><div className="card-head"><h2>Mudou desde a versão {p.version - 1}</h2></div>
          <div className="table-wrap" tabIndex={0}><table className="table diff-table"><thead><tr><th>Campo</th><th>Antes</th><th>Depois</th></tr></thead><tbody>{p.last_revision_diff.map(c => <tr key={c.label}><td><code className="code-inline">{c.label}</code></td><td>{c.before}</td><td>{c.after}</td></tr>)}</tbody></table></div>
        </section>}
        <section className="card">
          <div className="card-head"><h2>Conteúdo do plano</h2>{canEdit && !locked && <button className="button button-ghost button-sm" type="button" onClick={() => { setEditing(!editing); setJson(JSON.stringify(p.content, null, 2)); }}>{editing ? "Fechar edição" : "Editar"}</button>}</div>
          {editing && p.kind === "GOOGLE_SEARCH_CAMPAIGN"
            ? <CampaignEditor initial={p.content as SearchPlan} busy={busy === "save"} onSave={save}/>
            : editing
              ? <form onSubmit={e => { e.preventDefault(); try { void save(JSON.parse(json)); } catch { setError(new ApiError(0, "JSON inválido.")); } }}>
                <label className="field">JSON do plano<textarea className="textarea code" value={json} onChange={e => setJson(e.target.value)} spellCheck={false}/></label>
                <div className="form-actions"><button className="button button-primary" disabled={busy === "save"}>Salvar nova versão</button></div>
              </form>
              : <pre className="pre" tabIndex={0}>{JSON.stringify(p.content, null, 2)}</pre>}
        </section>
      </div>

      <aside>
        <section className="card">
          <div className="card-head"><h2>1. Validar</h2></div>
          <p className="muted">Confere política (limite do cliente, URL, kill switch) e pede à plataforma para checar a estrutura sem criar nada.</p>
          {validationCurrent && <ValidationBox validation={p.validation!}/>}
          {canEdit && !locked && <div className="form-actions"><button className="button button-ghost" type="button" disabled={busy !== null} onClick={() => act("validate", () => call(`/v1/plans/${p.id}/validate`, { method: "POST" }), "Validação concluída.")}>{busy === "validate" ? "Validando…" : validationCurrent ? "Validar de novo" : "Validar"}</button></div>}
        </section>

        <section className="card">
          <div className="card-head"><h2>2. Aprovar</h2><small>{PURPOSE_LABEL[p.purpose]}</small></div>
          <p className="muted">A aprovação vale só para esta versão (hash <code className="code-inline">{p.plan_hash.slice(0, 12)}…</code>). Qualquer edição exige nova aprovação.</p>
          {p.purpose === "ACTIVATE" && <div className="alert alert-warn"><strong>Esta proposta coloca anúncios no ar e começa a gastar.</strong></div>}
          {p.purpose === "BUDGET_CHANGE" && <label className="checkbox"><input type="checkbox" checked={funds} onChange={e => setFunds(e.target.checked)}/> {p.funds_confirmation_text} Sim.</label>}
          {p.approvals.slice(0, 3).map(a => <p key={a.id} className="muted">✓ v{a.version} aprovada por {a.approved_by} em {dateTimeBR(a.approved_at)}{a.consumed ? " · usada" : ""}</p>)}
          {canEdit && p.status === "VALIDATED" && <div className="form-actions"><button className="button button-primary" type="button" disabled={busy !== null || (p.purpose === "BUDGET_CHANGE" && !funds)}
            onClick={() => act("approve", () => call(`/v1/plans/${p.id}/approve`, { method: "POST", body: { plan_hash: p.plan_hash, confirm_funds: funds } }), "Aprovado.")}>{busy === "approve" ? "Aprovando…" : "Aprovar esta versão"}</button></div>}
        </section>

        <section className="card">
          <div className="card-head"><h2>3. Aplicar</h2></div>
          <p className="muted">{p.kind.endsWith("CAMPAIGN") ? "A campanha é criada pausada. Ativar é outra proposta." : "As alterações são aplicadas de uma vez e registradas com o estado anterior."}</p>
          {!mutationsOn && <div className="alert alert-warn"><strong>Aplicação desligada no servidor.</strong><span className="muted">Kill switch ligado ou plataforma sem permissão de escrita.</span></div>}
          {canEdit && p.status === "APPROVED" && <div className="form-actions"><button className="button button-violet" type="button" disabled={busy !== null || !mutationsOn || !executeKey}
            onClick={() => act("execute", () => call(`/v1/plans/${p.id}/execute`, { method: "POST", headers: { "Idempotency-Key": executeKey } }), "Enviado para execução.")}>{busy === "execute" ? "Enviando…" : "Aplicar na plataforma"}</button></div>}
        </section>
      </aside>
    </div>

    {p.executions.length > 0 && <section aria-label="Execuções">{p.executions.map(e => <ExecutionRow key={e.id} execution={e} canEdit={canEdit} onRevert={revert}/>)}</section>}
  </>;
}

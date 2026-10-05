"use client";

import { useState } from "react";
import { mutate as globalMutate } from "swr";
import { useApp, useApi } from "@/components/app/AppContext";
import { ErrorBox, Loading, PageHead } from "@/components/app/ui";
import { ApiError } from "@/lib/api";
import { dateTimeBR } from "@/lib/format";
import type { Role } from "@/lib/types";

type Members = { members: { user_id: string; name: string; email: string; role: Role }[]; pending_invitations: { id: string; email: string; role: Role; expires_at: string }[] };
const ROLE: Record<Role, string> = { owner: "Proprietário", admin: "Administrador", viewer: "Leitura" };

export default function Settings() {
  const { me, system, call, canEdit, isOwner, notify, setWorkspaceId } = useApp();
  const members = useApi<Members>("/v1/members");
  const [invite, setInvite] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function run(key: string, action: () => Promise<unknown>, success: string) {
    setBusy(key);
    try {
      await action();
      notify("ok", success);
      await Promise.all([members.mutate(), globalMutate(() => true)]);
    } catch (error) {
      notify("error", error instanceof ApiError ? [error.message, ...error.problems].join(" ") : "Não foi possível salvar.");
    } finally {
      setBusy(null);
    }
  }

  return <>
    <PageHead eyebrow="Conta" title="Configurações" text="Cliente atual, limites, equipe e segurança do seu acesso."/>
    <div className="grid-2">
      <section className="card">
        <div className="card-head"><h2>Cliente atual</h2></div>
        {!system ? <Loading/> : <form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget);
          const body: Record<string, unknown> = { name: f.get("name") };
          if (isOwner) body.daily_budget_limit = Number(f.get("limit")).toFixed(2);
          void run("ws", () => call("/v1/workspaces/current", { method: "PATCH", body }), "Cliente atualizado."); }}>
          <div className="form-grid">
            <label className="field">Nome<input className="input" name="name" defaultValue={system.workspace.name} key={system.workspace.id} disabled={!canEdit} required minLength={2} maxLength={120}/></label>
            <label className="field">Limite de orçamento diário <small>só o proprietário altera</small><input className="input" name="limit" type="number" step="0.01" min="0.01" defaultValue={system.workspace.daily_budget_limit} key={`l-${system.workspace.id}`} disabled={!isOwner}/></label>
          </div>
          <p className="muted">Nenhuma campanha nova ou mudança de orçamento acima deste valor passa na validação.</p>
          {canEdit && <div className="form-actions"><button className="button button-primary button-sm" disabled={busy === "ws"}>Salvar</button></div>}
        </form>}
      </section>

      {canEdit && <section className="card">
        <div className="card-head"><h2>Novo cliente</h2></div>
        <form onSubmit={e => { e.preventDefault(); const form = e.currentTarget; const f = new FormData(form);
          void run("new-ws", async () => { const created = await call<{ id: string }>("/v1/workspaces", { method: "POST", body: { name: f.get("name"), daily_budget_limit: Number(f.get("limit")).toFixed(2) } }); form.reset(); setWorkspaceId(created.id); }, "Cliente criado e selecionado."); }}>
          <div className="form-grid">
            <label className="field">Nome do cliente<input className="input" name="name" required minLength={2} maxLength={120}/></label>
            <label className="field">Limite diário inicial<input className="input" name="limit" type="number" step="0.01" min="0.01" defaultValue="100.00" required/></label>
          </div>
          <div className="form-actions"><button className="button button-ghost button-sm" disabled={busy === "new-ws"}>Criar cliente</button></div>
        </form>
      </section>}
    </div>

    <section className="card">
      <div className="card-head"><h2>Equipe da organização</h2></div>
      {members.error ? <ErrorBox error={members.error}/> : !members.data ? <Loading/> : <>
        <div className="table-wrap" tabIndex={0}><table className="table"><thead><tr><th>Nome</th><th>E-mail</th><th>Papel</th>{isOwner && <th/>}</tr></thead><tbody>
          {members.data.members.map(m => <tr key={m.user_id}><td>{m.name}{m.user_id === me?.user.id ? " (você)" : ""}</td><td>{m.email}</td>
            <td>{isOwner && m.user_id !== me?.user.id ? <select className="select" aria-label={`Papel de ${m.name}`} value={m.role} onChange={e => run(`role-${m.user_id}`, () => call(`/v1/members/${m.user_id}`, { method: "PATCH", body: { role: e.target.value } }), "Papel alterado.")}>
              {(Object.keys(ROLE) as Role[]).map(r => <option key={r} value={r}>{ROLE[r]}</option>)}</select> : ROLE[m.role]}</td>
            {isOwner && <td>{m.user_id !== me?.user.id && <button className="button button-danger button-sm" type="button" onClick={() => { if (confirm(`Remover ${m.name} da organização?`)) void run(`rm-${m.user_id}`, () => call(`/v1/members/${m.user_id}`, { method: "DELETE" }), "Membro removido."); }}>Remover</button>}</td>}
          </tr>)}
        </tbody></table></div>
        {members.data.pending_invitations.length > 0 && <><h3>Convites pendentes</h3><ul className="list-plain">{members.data.pending_invitations.map(i => <li key={i.id} className="account-row"><span>{i.email}<small>{ROLE[i.role]} · expira {dateTimeBR(i.expires_at)}</small></span>
          <button className="button button-ghost button-sm" type="button" onClick={() => run(`inv-${i.id}`, () => call(`/v1/invitations/${i.id}`, { method: "DELETE" }), "Convite cancelado.")}>Cancelar</button></li>)}</ul></>}
      </>}
      {canEdit && <form className="form-grid card" onSubmit={e => { e.preventDefault(); const form = e.currentTarget; const f = new FormData(form);
        void run("invite", async () => { const data = await call<{ invite_url: string }>("/v1/invitations", { method: "POST", body: { email: f.get("email"), role: f.get("role") } }); setInvite(data.invite_url); form.reset(); }, "Convite criado. Envie o link à pessoa."); }}>
        <label className="field">E-mail da pessoa<input className="input" name="email" type="email" required autoComplete="off" spellCheck={false}/></label>
        <label className="field">Papel<select className="select" name="role" defaultValue="viewer"><option value="viewer">Leitura</option><option value="admin">Administrador</option>{isOwner && <option value="owner">Proprietário</option>}</select></label>
        <div className="form-actions full"><button className="button button-primary button-sm" disabled={busy === "invite"}>Gerar convite</button><small className="muted">O link vale por 7 dias e só pode ser usado uma vez.</small></div>
        {invite && <div className="full alert alert-ok"><strong>Link do convite (aparece só agora):</strong><code className="code-inline">{invite}</code>
          <div><button className="button button-ghost button-sm" type="button" onClick={() => navigator.clipboard?.writeText(invite).then(() => notify("ok", "Link copiado."))}>Copiar link</button></div></div>}
      </form>}
    </section>

    <section className="card">
      <div className="card-head"><h2>Sua senha</h2></div>
      <form onSubmit={e => { e.preventDefault(); const form = e.currentTarget; const f = new FormData(form);
        if (f.get("new") !== f.get("confirm")) { notify("error", "As senhas novas não conferem."); return; }
        void run("pwd", async () => { await call("/v1/auth/password", { method: "POST", body: { current_password: f.get("current"), new_password: f.get("new") } }); form.reset(); }, "Senha alterada. Outras sessões foram encerradas."); }}>
        <div className="form-grid">
          <label className="field">Senha atual<input className="input" name="current" type="password" autoComplete="current-password" required/></label>
          <span/>
          <label className="field">Nova senha <small>10+ caracteres, letras e números</small><input className="input" name="new" type="password" autoComplete="new-password" required minLength={10}/></label>
          <label className="field">Confirme<input className="input" name="confirm" type="password" autoComplete="new-password" required minLength={10}/></label>
        </div>
        <div className="form-actions"><button className="button button-ghost button-sm" disabled={busy === "pwd"}>Alterar senha</button></div>
      </form>
    </section>
  </>;
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Arrow } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

type Info = { email: string; role: string; organization: string; existing_user: boolean };
const ROLE: Record<string, string> = { owner: "proprietário", admin: "administrador", viewer: "leitura" };

export function AcceptInvite({ token }: { token: string }) {
  const router = useRouter();
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Info>(`/v1/invitations/${encodeURIComponent(token)}`).then(setInfo).catch((failure: unknown) =>
      setError(failure instanceof ApiError ? failure.message : "Convite indisponível."));
  }, [token]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (!info?.existing_user && form.get("password") !== form.get("confirm")) {
      setError("As senhas não conferem.");
      return;
    }
    setBusy(true);
    setError(null);
    setProblems([]);
    try {
      await api(`/v1/invitations/${encodeURIComponent(token)}/accept`, { method: "POST", body: { name: form.get("name") || "—", password: form.get("password") } });
      router.replace("/app");
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Não foi possível aceitar o convite.");
      setProblems(failure instanceof ApiError ? failure.problems : []);
      setBusy(false);
    }
  }

  if (!info && !error) return <div className="skeleton" aria-label="Carregando convite"/>;
  if (!info) return <div><h2>Convite indisponível</h2><div className="alert alert-error" role="alert"><strong>{error}</strong></div><p className="auth-foot">Peça um novo convite a quem enviou este link. <Link href="/entrar">Ir para o login</Link></p></div>;

  return <div>
    <h2>Você foi convidado</h2>
    <p className="muted">Entre em <strong>{info.organization}</strong> com acesso de <strong>{ROLE[info.role] ?? info.role}</strong>, como {info.email}.</p>
    <form onSubmit={submit}>
      {error && <div className="alert alert-error" role="alert"><strong>{error}</strong>{problems.length > 0 && <ul>{problems.map(p => <li key={p}>{p}</li>)}</ul>}</div>}
      {!info.existing_user && <label className="field">Seu nome<input className="input" name="name" autoComplete="name" required minLength={2} maxLength={120} autoCapitalize="words"/></label>}
      <label className="field">{info.existing_user ? "Sua senha atual" : "Crie uma senha"}{!info.existing_user && <small>Mínimo de 10 caracteres, com letras e números.</small>}
        <input className="input" name="password" type="password" autoComplete={info.existing_user ? "current-password" : "new-password"} required minLength={info.existing_user ? 1 : 10} maxLength={200}/></label>
      {!info.existing_user && <label className="field">Confirme a senha<input className="input" name="confirm" type="password" autoComplete="new-password" required minLength={10} maxLength={200}/></label>}
      <button className="button button-primary button-block" disabled={busy}>{busy ? "Entrando…" : <>Aceitar e entrar <Arrow/></>}</button>
    </form>
  </div>;
}

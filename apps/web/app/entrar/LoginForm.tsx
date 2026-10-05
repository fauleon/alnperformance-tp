"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { Arrow } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { whatsapp } from "@/lib/site";

function safeNext(value: string | null): string {
  return value && value.startsWith("/app") && !value.startsWith("//") ? value : "/app";
}

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api("/v1/auth/login", { method: "POST", body: { email: form.get("email"), password: form.get("password") } });
      router.replace(safeNext(params.get("next")));
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Não foi possível entrar.");
      requestAnimationFrame(() => errorRef.current?.focus());
      setBusy(false);
    }
  }

  return <form onSubmit={submit} noValidate>
    {error && <div className="alert alert-error" role="alert" tabIndex={-1} ref={errorRef}><strong>{error}</strong></div>}
    <label className="field">E-mail<input className="input" name="email" type="email" autoComplete="email" required maxLength={254} spellCheck={false} autoCapitalize="off"/></label>
    <label className="field">Senha<input className="input" name="password" type="password" autoComplete="current-password" required maxLength={200}/></label>
    <button className="button button-primary button-block" type="submit" disabled={busy}>{busy ? "Entrando…" : <>Entrar <Arrow/></>}</button>
    <p className="auth-foot">Ainda não tem acesso? <a href={whatsapp("Olá, quero acesso ao ALN Hub ia.")} target="_blank" rel="noopener noreferrer">Fale com a ALN</a>. · <Link href="/">Voltar ao site</Link></p>
  </form>;
}

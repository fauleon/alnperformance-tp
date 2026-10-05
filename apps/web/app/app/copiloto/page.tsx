"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useApp } from "@/components/app/AppContext";
import { useCreatePlan } from "@/components/app/hooks";
import { PageHead } from "@/components/app/ui";
import { ApiError } from "@/lib/api";
import type { PlanKind } from "@/lib/types";

type Proposal = { kind: PlanKind; content: Record<string, unknown> | null; error: string | null };
type Message = { role: "user" | "assistant"; content: string; proposal?: Proposal | null };
type Reply = { reply: string; proposal: Proposal | null; ai_enabled: boolean; can_propose: boolean };

const SUGGESTIONS = [
  "Faça um diagnóstico da conta e diga o que corrigir primeiro.",
  "Quais termos de pesquisa estão gastando sem converter?",
  "Os meus anúncios estão bons? Sugira títulos melhores.",
  "Vale trocar a estratégia de lance agora?",
];

function describe(proposal: Proposal): string {
  const changes = (proposal.content?.changes as { action: string }[] | undefined) ?? [];
  return changes.length ? changes.map(c => c.action.replaceAll("_", " ").toLowerCase()).join(", ") : "campanha nova";
}

export default function Copilot() {
  const { account, call, canEdit } = useApp();
  const router = useRouter();
  const createPlan = useCreatePlan();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => { logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" }); }, [messages, busy]);
  useEffect(() => { setMessages([]); }, [account?.id]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages(current => [...current, { role: "user", content: message }]);
    setInput("");
    setBusy(true);
    try {
      const reply = await call<Reply>("/v1/copilot/chat", { method: "POST", body: { account_id: account?.id ?? null, message, history } });
      setMessages(current => [...current, { role: "assistant", content: reply.reply, proposal: reply.proposal }]);
    } catch (error) {
      setMessages(current => [...current, { role: "assistant", content: error instanceof ApiError ? error.message : "Não consegui responder agora." }]);
    } finally {
      setBusy(false);
    }
  }

  async function adopt(proposal: Proposal) {
    if (!proposal.content) return;
    const id = await createPlan(proposal.kind, proposal.content, "copilot");
    if (id) router.push(`/app/planos/${id}`);
  }

  return <>
    <PageHead eyebrow="Estratégia assistida" title="Copiloto de IA" text={account ? `Conversando sobre ${account.name}. O copiloto lê os dados da conta e só propõe — você aprova.` : "Conecte uma conta para o copiloto analisar dados reais."}/>
    <section className="chat" aria-label="Conversa com o copiloto">
      <div className="chat-log" ref={logRef} aria-live="polite">
        {messages.length === 0 && <div className="empty">
          <h2>Pergunte sobre a sua conta</h2>
          <p>Exemplos para começar:</p>
          <div className="suggestions">{SUGGESTIONS.map(s => <button key={s} type="button" onClick={() => send(s)}>{s}</button>)}</div>
        </div>}
        {messages.map((m, i) => <div key={i} className={`msg ${m.role}`}>
          {m.content}
          {m.proposal && <div className="proposal">
            {m.proposal.error ? <p className="text-warn">{m.proposal.error}</p> : <>
              <b>Proposta pronta:</b> {describe(m.proposal)}
              <div className="form-actions">{canEdit
                ? <button className="button button-primary button-sm" type="button" onClick={() => adopt(m.proposal!)}>Criar proposta para revisão</button>
                : <small className="muted">Só administradores criam propostas.</small>}</div>
            </>}
          </div>}
        </div>)}
        {busy && <div className="msg assistant" role="status">Analisando a conta…</div>}
      </div>
      <form className="chat-form" onSubmit={event => { event.preventDefault(); void send(input); }}>
        <label className="visually-hidden" htmlFor="chat-input">Mensagem</label>
        <textarea id="chat-input" className="textarea" value={input} maxLength={4000} placeholder="Escreva sua pergunta…" onChange={event => setInput(event.target.value)}
          onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(input); } }}/>
        <button className="button button-primary" disabled={busy || !input.trim()}>Enviar</button>
      </form>
    </section>
  </>;
}

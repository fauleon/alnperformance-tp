"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { STATUS_LABEL } from "@/lib/format";

export function PageHead({ eyebrow, title, text, actions }: { eyebrow: string; title: string; text?: ReactNode; actions?: ReactNode }) {
  return <div className="page-head">
    <div><p className="eyebrow"><span className="status-dot"/> {eyebrow}</p><h1>{title}</h1>{text && <p>{text}</p>}</div>
    {actions && <div className="actions">{actions}</div>}
  </div>;
}

const TONE: Record<string, string> = {
  EXECUTED: "ok", SUCCEEDED: "ok", ENABLED: "ok", ENABLE: "ok", ACTIVE: "ok", VALIDATED: "info", APPROVED: "info",
  QUEUED: "warn", RUNNING: "warn", RETRYING: "warn", DRAFT: "", PAUSED: "warn", DISABLE: "warn",
  BLOCKED: "bad", FAILED: "bad", REMOVED: "bad", NEEDS_RECONNECT: "bad", ARCHIVED: "",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = TONE[status] ?? "";
  return <span className={`badge${tone ? ` badge-${tone}` : ""}`}>{STATUS_LABEL[status] ?? status}</span>;
}

export function Kpi({ label, value }: { label: string; value: string }) {
  return <div className="kpi"><small>{label}</small><b>{value}</b></div>;
}

export function Empty({ title, text, action }: { title: string; text: ReactNode; action?: ReactNode }) {
  return <div className="empty"><h2>{title}</h2><p>{text}</p>{action}</div>;
}

export function Loading({ label = "Carregando" }: { label?: string }) {
  return <div className="skeleton" role="status" aria-label={label}/>;
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof ApiError ? error.message : "Algo deu errado ao carregar.";
  const problems = error instanceof ApiError ? error.problems : [];
  const reconnect = error instanceof ApiError && error.needsReconnect;
  return <div className="alert alert-error" role="alert">
    <strong>{message}</strong>
    {problems.length > 0 && <ul>{problems.slice(0, 8).map(p => <li key={p}>{p}</li>)}</ul>}
    <div className="form-actions">
      {reconnect && <Link className="button button-primary button-sm" href="/app/integracoes">Reconectar conta</Link>}
      {onRetry && <button className="button button-ghost button-sm" type="button" onClick={onRetry}>Tentar de novo</button>}
    </div>
  </div>;
}

export function NoAccount() {
  return <Empty title="Conecte uma conta de anúncio" text="Autorize o Google Ads ou o TikTok Ads e escolha a conta deste cliente para ver dados reais."
    action={<Link className="button button-primary" href="/app/integracoes">Ir para Integrações</Link>}/>;
}

export function LineChart({ points, label, format }: { points: { x: string; y: number }[]; label: string; format: (v: number) => string }) {
  const W = 800, H = 240, P = { l: 56, r: 16, t: 16, b: 30 };
  if (points.length === 0) return <p className="muted">Sem dados no período.</p>;
  const max = Math.max(...points.map(p => p.y), 0) || 1;
  const step = points.length > 1 ? (W - P.l - P.r) / (points.length - 1) : 0;
  const xy = points.map((p, i) => [P.l + i * step, H - P.b - (p.y / max) * (H - P.t - P.b)] as const);
  const line = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${xy[xy.length - 1][0].toFixed(1)},${H - P.b} L${P.l},${H - P.b} Z`;
  const ticks = [0, 0.5, 1].map(f => ({ y: H - P.b - f * (H - P.t - P.b), v: f * max }));
  const labelEvery = Math.max(1, Math.ceil(points.length / 8));
  const total = points.reduce((sum, p) => sum + p.y, 0);
  return <figure className="chart">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${label}: total ${format(total)}, máximo diário ${format(max)}, ${points.length} dias.`}>
      <defs><linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#dafa73" stopOpacity=".28"/><stop offset="1" stopColor="#dafa73" stopOpacity="0"/></linearGradient></defs>
      {ticks.map(t => <g key={t.y}><line className="grid" x1={P.l} x2={W - P.r} y1={t.y} y2={t.y}/><text className="label" x={P.l - 8} y={t.y + 4} textAnchor="end">{format(t.v)}</text></g>)}
      <path className="area" d={area}/>
      <path className="series" d={line}/>
      {xy.map(([x, y], i) => <circle key={points[i].x} className="dot" cx={x} cy={y} r={points.length > 40 ? 0 : 3}><title>{`${points[i].x}: ${format(points[i].y)}`}</title></circle>)}
      {points.map((p, i) => i % labelEvery === 0 && <text key={p.x} className="label" x={xy[i][0]} y={H - 8} textAnchor="middle">{p.x}</text>)}
    </svg>
  </figure>;
}

export function BarList({ items, format }: { items: { label: string; value: number }[]; format: (v: number) => string }) {
  const max = Math.max(...items.map(i => i.value), 0) || 1;
  return <div className="bars">{items.map(item => <div className="bar-row" key={item.label}>
    <div><div>{item.label}</div><svg viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true"><rect className="track" width="100" height="8" rx="4"/><rect className="fill" width={Math.max(1, (item.value / max) * 100)} height="8" rx="4"/></svg></div>
    <div className="num">{format(item.value)}</div>
  </div>)}</div>;
}

export function ScoreRing({ score }: { score: number }) {
  const r = 40, c = 2 * Math.PI * r, color = score >= 80 ? "#4ade80" : score >= 50 ? "#fbbf24" : "#ff7b7b";
  return <svg viewBox="0 0 96 96" role="img" aria-label={`Nota ${score} de 100`}>
    <circle className="ring-bg" cx="48" cy="48" r={r}/>
    <circle className="ring" cx="48" cy="48" r={r} stroke={color} strokeDasharray={`${(score / 100) * c} ${c}`} transform="rotate(-90 48 48)"/>
    <text x="48" y="55" textAnchor="middle" fontSize="24">{score}</text>
  </svg>;
}

export function Toast({ toast }: { toast: { kind: "ok" | "error"; text: string } | null }) {
  return <div aria-live="polite" role="status">{toast && <div className={`toast ${toast.kind}`}>{toast.text}</div>}</div>;
}

export function customerId(id: string): string {
  return /^\d{10}$/.test(id) ? `${id.slice(0, 3)}-${id.slice(3, 6)}-${id.slice(6)}` : id;
}

export function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

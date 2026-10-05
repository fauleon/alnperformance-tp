"use client";

import { useState } from "react";
import { useApp } from "@/components/app/AppContext";
import { ApiError } from "@/lib/api";

export type Geo = { id: string; name: string };
type Suggestion = { id: string; name: string; canonical_name: string; type: string; reach: number };

export function GeoPicker({ value, onChange }: { value: Geo[]; onChange: (geos: Geo[]) => void }) {
  const { account, call } = useApp();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Suggestion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function search() {
    if (!account || query.trim().length < 2) return;
    setBusy(true);
    setError(null);
    try {
      const data = await call<{ suggestions: Suggestion[] }>(`/v1/accounts/${account.id}/geo-suggest?q=${encodeURIComponent(query.trim())}`);
      setResults(data.suggestions);
      if (!data.suggestions.length) setError("Nenhum local encontrado.");
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Busca indisponível. Informe o ID do local.");
    } finally {
      setBusy(false);
    }
  }

  function add(geo: Geo) {
    if (!value.some(v => v.id === geo.id)) onChange([...value, geo]);
    setResults([]);
    setQuery("");
  }

  return <div className="field">
    <span>Localização <small>(segmentação por presença)</small></span>
    <div className="chips">{value.map(g => <span className="chip" key={g.id}>{g.name} <button type="button" aria-label={`Remover ${g.name}`} onClick={() => onChange(value.filter(v => v.id !== g.id))}>×</button></span>)}</div>
    <div className="form-actions">
      <input className="input" value={query} onChange={e => setQuery(e.target.value)} placeholder="Cidade, bairro ou estado (ou ID numérico)" aria-label="Buscar localização"
        onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); if (/^\d+$/.test(query.trim())) add({ id: query.trim(), name: `ID ${query.trim()}` }); else void search(); } }}/>
      <button className="button button-ghost button-sm" type="button" onClick={() => /^\d+$/.test(query.trim()) ? add({ id: query.trim(), name: `ID ${query.trim()}` }) : search()} disabled={busy}>{busy ? "Buscando…" : "Adicionar"}</button>
    </div>
    {error && <small className="text-warn">{error}</small>}
    {results.length > 0 && <ul className="list-plain" aria-label="Sugestões">{results.map(r => <li key={r.id}><button className="row-button" type="button" onClick={() => add({ id: r.id, name: r.name })}>{r.canonical_name}</button> <small className="muted">{r.type}{r.reach ? ` · alcance ${r.reach.toLocaleString("pt-BR")}` : ""}</small></li>)}</ul>}
  </div>;
}

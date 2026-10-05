const number = new Intl.NumberFormat("pt-BR");
const decimal = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function money(value: string | number | null | undefined, currency = "BRL"): string {
  if (value === null || value === undefined || value === "") return "—";
  try {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(Number(value));
  } catch {
    return `${decimal.format(Number(value))} ${currency}`;
  }
}

export const int = (value: number | string | null | undefined) => (value === null || value === undefined ? "—" : number.format(Number(value)));
export const dec = (value: number | string | null | undefined) => (value === null || value === undefined || value === "" ? "—" : decimal.format(Number(value)));
export const pct = (value: number | string | null | undefined) => (value === null || value === undefined ? "—" : `${decimal.format(Number(value))}%`);

export function dateBR(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString("pt-BR");
}

export function dateTimeBR(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export const STATUS_LABEL: Record<string, string> = {
  DRAFT: "Rascunho", VALIDATED: "Validado", BLOCKED: "Bloqueado", APPROVED: "Aprovado", QUEUED: "Na fila", EXECUTED: "Executado",
  FAILED: "Falhou", ARCHIVED: "Arquivado", ENABLED: "Ativa", PAUSED: "Pausada", REMOVED: "Removida", ENABLE: "Ativa", DISABLE: "Pausada",
  SUCCEEDED: "Concluída", RUNNING: "Executando", RETRYING: "Tentando de novo", ACTIVE: "Conectada", NEEDS_RECONNECT: "Reconectar",
};

export const KIND_LABEL: Record<string, string> = {
  GOOGLE_SEARCH_CAMPAIGN: "Nova campanha · Google Pesquisa", GOOGLE_CHANGE: "Alteração · Google Ads",
  TIKTOK_CAMPAIGN: "Nova campanha · TikTok", TIKTOK_CHANGE: "Alteração · TikTok Ads",
};

export const PURPOSE_LABEL: Record<string, string> = {
  CREATE_PAUSED: "Criar pausada", APPLY_CHANGE: "Aplicar alteração", ACTIVATE: "Ativação (aprovação separada)", BUDGET_CHANGE: "Mudança de orçamento",
};

export const SEVERITY_LABEL: Record<string, string> = { critical: "Crítico", high: "Alto", medium: "Médio", low: "Baixo" };
export const PROVIDER_LABEL: Record<string, string> = { GOOGLE_ADS: "Google Ads", TIKTOK_ADS: "TikTok Ads" };
export const BIDDING_LABEL: Record<string, string> = {
  TARGET_SPEND: "Maximizar cliques", MAXIMIZE_CLICKS: "Maximizar cliques", MAXIMIZE_CONVERSIONS: "Maximizar conversões", MANUAL_CPC: "CPC manual",
  TARGET_CPA: "CPA desejado", TARGET_ROAS: "ROAS desejado", MAXIMIZE_CONVERSION_VALUE: "Maximizar valor", TARGET_IMPRESSION_SHARE: "Parcela de impressões",
};

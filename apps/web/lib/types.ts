export type Role = "owner" | "admin" | "viewer";
export type ProviderId = "GOOGLE_ADS" | "TIKTOK_ADS";

export type Me = {
  user: { id: string; name: string; email: string };
  organizations: { id: string; name: string; role: Role }[];
  workspaces: { id: string; name: string; organization_id: string; role: Role; daily_budget_limit: string }[];
};

export type SystemInfo = {
  kill_switch: boolean; ai_enabled: boolean; google_mutations: boolean; tiktok_mutations: boolean; role: Role;
  workspace: { id: string; name: string; daily_budget_limit: string };
};

export type AdAccount = {
  id: string; provider: ProviderId; external_id: string; name: string; currency: string | null; time_zone: string | null;
  login_customer_id: string | null; is_test_account: boolean; connection_id: string;
};

export type Discovered = {
  external_id: string; name: string; currency: string | null; login_customer_id: string | null; is_manager: boolean;
  is_test_account: boolean; selectable: boolean; parent_name: string | null;
};

export type Connection = { id: string; provider: ProviderId; status: string; created_at: string; last_error: string | null; discovered_accounts: Discovered[] };

export type ProviderInfo = { provider: ProviderId; name: string; readable: string[]; editable: string[]; configured: boolean; mutations_enabled: boolean; excluded: string[] };

export type Metrics = {
  impressions: number; clicks: number; cost: string; conversions: string; conversion_value: string;
  ctr?: string | null; cpc?: string | null; cost_per_conversion?: string | null;
};

export type Keyword = { criterion_id: string; text: string; match_type: string; status: string; quality_score: number | null; metrics: Metrics };
export type Ad = { ad_id: string; type: string; status: string; headlines: string[]; descriptions: string[]; ad_strength: string | null; final_urls: string[]; metrics: Metrics };
export type AdGroup = { ad_group_id: string; name: string; status: string; keywords: Keyword[]; ads: Ad[]; metrics: Metrics };
export type Campaign = {
  campaign_id: string; name: string; status: string; channel: string; bidding_strategy: string | null; daily_budget: string | null;
  start_date: string | null; end_date: string | null; search_partners: boolean | null; display_network: boolean | null;
  geo_target_type: string | null; geo_targets: string[]; negatives: { criterion_id: string | null; text: string; match_type: string; source: string }[];
  assets: { type: string; text: string }[]; ad_groups: AdGroup[]; metrics: Metrics; objective: string | null; has_pixel: boolean | null;
};

export type Snapshot = {
  provider: ProviderId; account_id: string; account_name: string | null; currency: string | null; period_start: string; period_end: string;
  campaigns: Campaign[]; conversion_actions: { conversion_action_id: string; name: string; status: string; category: string | null; primary: boolean; conversions: string }[];
  enhanced_conversions_for_leads: boolean | null;
  search_terms: { term: string; campaign_id: string; ad_group_id: string | null; status: string | null; metrics: Metrics }[];
  totals: Metrics; by_day: (Metrics & { day: string })[]; campaign_metrics: Record<string, Metrics>;
};

export type Finding = {
  rule: string; severity: "critical" | "high" | "medium" | "low"; title: string; why: string; fix: string;
  campaign_id: string | null; campaign_name: string | null; evidence: Record<string, unknown>; proposal: Record<string, unknown> | null;
};
export type AuditReport = { provider: ProviderId; account_id: string; score: number; findings: Finding[]; summary: Record<string, number>; period_start: string; period_end: string };

export type PlanKind = "GOOGLE_SEARCH_CAMPAIGN" | "GOOGLE_CHANGE" | "TIKTOK_CAMPAIGN" | "TIKTOK_CHANGE";
export type PlanStatus = "DRAFT" | "VALIDATED" | "BLOCKED" | "APPROVED" | "QUEUED" | "EXECUTED" | "FAILED" | "ARCHIVED";

export type PlanSummary = {
  id: string; kind: PlanKind; provider: ProviderId; title: string; status: PlanStatus; version: number; source: string;
  account_id: string | null; plan_hash: string; created_at: string; updated_at: string; reverts_execution_id: string | null;
};

export type Validation = {
  allowed: boolean; plan_hash: string; plan_version: number; violations: string[]; warnings: string[];
  remote_status: "ok" | "rejected" | "unavailable" | "skipped"; remote_errors: string[]; purpose: string; validated_at: string;
};

export type Execution = {
  id: string; plan_id: string; status: string; idempotency_key: string; result: Record<string, unknown> | null; error: string | null;
  before: Record<string, unknown> | null; after: Record<string, unknown> | null; created_at: string; finished_at: string | null;
};

export type PlanDetail = PlanSummary & {
  content: Record<string, unknown>; validation: Validation | null; purpose: string; funds_confirmation_text: string;
  account: { id: string; name: string; external_id: string; currency: string | null } | null;
  changes: { label: string; before: string; after: string }[];
  revisions: { version: number; created_at: string; content_hash: string }[];
  last_revision_diff: { label: string; before: string; after: string }[];
  approvals: { id: string; version: number; purpose: string; approved_by: string; approved_at: string; consumed: boolean; financial_confirmation: boolean }[];
  executions: Execution[];
};

export type AuditEvent = { id: string; action: string; actor: string; resource_type: string; resource_id: string; result: string; details: Record<string, unknown> | null; occurred_at: string };

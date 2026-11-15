export type Language = "en" | "hi" | "ne";
export interface Health {
  status: string;
  models_loaded: boolean;
  detail?: string | null;
}
export interface System {
  genai: {
    configured: boolean;
    provider: string;
    generation: string;
    context_ttl_seconds: number;
  };
  demo_enabled: boolean;
  towns: Record<string, string>;
  data_sources: string[];
  limitations: string[];
}
export interface Period {
  type: string;
  start?: string | null;
  end?: string | null;
  value?: number | null;
  unit?: string | null;
}
export interface Query {
  schema_version: string;
  intent: string;
  operation: string;
  answer_kind: string;
  locations: {
    id: string;
    name: string;
    type: string;
    parent?: string | null;
  }[];
  variables: string[];
  disasters: string[];
  time_period: Period | null;
  context_used: string[];
  scenario?: unknown;
  target?: unknown;
}
export interface Analysis {
  language: { code: Language; confidence: number };
  intent: { label: string; confidence: number };
  entities: {
    text: string;
    type: string;
    normalized: string | null;
    start: number;
    end: number;
    confidence: number;
  }[];
  structured_query: Query | null;
  status: string;
  clarification?: {
    reason: string;
    message_key: string;
    missing_fields: string[];
  } | null;
  warnings: string[];
}
export interface Daily {
  date: string;
  temperature_mean_c: number | null;
  temperature_min_c: number | null;
  temperature_max_c: number | null;
  precipitation_mm: number | null;
  rainfall_mm: number | null;
}
export interface Weather {
  location_id: string;
  location_name: string;
  start: string;
  end: string;
  timezone: string;
  data_kind: string;
  source: string;
  source_url: string;
  attribution: string;
  license_url: string;
  retrieved_at: string;
  requested_latitude: number;
  requested_longitude: number;
  grid_latitude: number;
  grid_longitude: number;
  daily: Daily[];
  summary: {
    days: number;
    temperature_mean_c: number | null;
    temperature_min_c: number | null;
    temperature_max_c: number | null;
    precipitation_total_mm: number | null;
    rainfall_total_mm: number | null;
    valid_days: Record<string, number>;
    totals_complete: boolean;
    interpretation: string;
  };
  warnings: string[];
}
export interface Environment {
  status: string;
  message: string | null;
  query: Query;
  results: Weather[];
  errors: string[];
}
export interface Explanation {
  status:
    | "ok"
    | "disabled"
    | "unavailable"
    | "rejected"
    | "no_context"
    | "unsupported";
  message: string;
  language: Language;
  text: string | null;
  claims: {
    fact_id: string;
    value: string;
    unit: string;
    metric: string;
    start: string;
    end: string;
    location_names: string[];
    source_ids: string[];
    coverage: string;
  }[];
  sources: {
    id: string;
    name: string;
    url: string;
    attribution: string;
    data_kind: string;
    retrieved_at: string;
    source_mode: string;
  }[];
  provider: string | null;
  model: string | null;
}
export interface Bundle {
  environment: Environment;
  context_id: string | null;
  explanation: Explanation;
}
export type Mode = "trained" | "demo";
export type SourceMode = "live" | "snapshot";
export interface Run {
  question: string;
  mode: Mode;
  source: SourceMode;
  analysis: Analysis;
  bundle: Bundle | null;
}

/** Preflight routing is deterministic; it is never a trained-model prediction. */
export interface QuestionRoute {
  category:
    | "environment"
    | "general_knowledge"
    | "contextual"
    | "unsupported"
    | "clarification";
  message: string;
  knowledge: null | {
    topic: string;
    title: string;
    text: string;
    language: Language;
    label: string;
    sources: { name: string; url: string }[];
  };
}

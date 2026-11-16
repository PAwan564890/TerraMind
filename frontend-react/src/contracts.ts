export type Language = "en" | "hi" | "ne";
export interface Health {
  status: string;
  models_loaded: boolean;
  detail?: string | null;
}
export interface System {
  capabilities?: {
    extended_locations: boolean;
    additional_measurements: string[];
    locations_endpoint: string;
    insights_endpoint: string;
  };
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
  measurements?: MeasurementResponse;
  insights?: InsightResponse;
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

export interface TownPoint {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  country_code: string;
  admin1: string;
  admin2: string | null;
  aliases: Record<string, string[]>;
  geonames_id: number;
  source_url: string;
  attribution: string;
  verified_at: string;
  legacy: boolean;
}
export interface LocationRegistry {
  extended_enabled: boolean;
  locations: TownPoint[];
  supplemental_variables: string[];
  limitation: string;
}
export interface EventDay {
  value: number;
  date: string;
  tied_dates: string[];
}
export interface TemporalInsight {
  location_name?: string;
  location_id: string;
  start: string;
  end: string;
  timezone: string;
  temperature_days: { highest: EventDay | null; lowest: EventDay | null };
  rainfall_days: { highest: EventDay | null; lowest: EventDay | null };
  period_temperature_range_c: number | null;
  daily_variation: { date: string; temperature_range_c: number | null }[];
  day_to_day: {
    date: string;
    previous_date: string;
    temperature_mean_change_c: number | null;
  }[];
  monthly: {
    month: string;
    retrieved_days: number;
    temperature_valid_days: number;
    rainfall_valid_days: number;
    temperature_mean_c: number | null;
    rainfall_total_mm: number | null;
    period_start: string;
    period_end: string;
    label: string;
  }[];
  coverage: Record<
    string,
    { valid: number; missing: number; expected: number }
  >;
  tie_rule: string;
  limitation: string;
}
export interface InsightResponse {
  status: string;
  source_mode?: string;
  message?: string | null;
  results: TemporalInsight[];
  comparisons: {
    left: string;
    right: string;
    left_name?: string;
    right_name?: string;
    warmer_name?: string | null;
    wetter_name?: string | null;
    start: string;
    end: string;
    temperature_difference_c: number | null;
    rainfall_difference_mm: number | null;
    warmer: string | null;
    wetter: string | null;
    warnings: string[];
  }[];
}
export interface MeasurementResponse {
  status: string;
  message: string | null;
  errors: string[];
  query: Query;
  results: {
    location_id: string;
    location_name: string;
    start: string;
    end: string;
    timezone: string;
    data_kind: string;
    source: string;
    source_url: string;
    attribution: string;
    retrieved_at: string;
    requested_latitude: number;
    requested_longitude: number;
    grid_latitude: number;
    grid_longitude: number;
    daily: ({ date: string } & Record<string, number | string | null>)[];
    summary: Record<
      string,
      {
        mean: number | null;
        minimum: number | null;
        maximum: number | null;
        unit: string;
        valid_days: number;
        missing_days: number;
        expected_days: number;
      }
    >;
    limitations: string[];
  }[];
}
export interface SelectedBundle extends Bundle {
  insights: InsightResponse;
  inference: string;
}

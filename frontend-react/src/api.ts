import type {
  Analysis,
  Bundle,
  Health,
  System,
  Query,
  Language,
  Mode,
  SourceMode,
  Explanation,
  QuestionRoute,
  LocationRegistry,
  InsightResponse,
  MeasurementResponse,
  SelectedBundle,
} from "./contracts";
export class APIError extends Error {}
export async function request<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener("abort", cancel, { once: true });
  if (signal?.aborted) controller.abort();
  const timer = setTimeout(() => controller.abort(), 100_000);
  try {
    const response = await fetch(
      `${(import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "")}${path}`,
      {
        method: body === undefined ? "GET" : "POST",
        headers:
          body === undefined ? {} : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      },
    );
    if (!response.ok) {
      const messages: Record<number, string> = {
        503: "Trained NLP is unavailable. Restore checkpoints or explicitly select rule demonstration.",
        404: "Route unavailable. Start backend.presentation.app; rule demonstration requires TERRAMIND_DEMO=1.",
        422: "The backend rejected this input. Check dates, chronological order and supported retrieval limits.",
      };
      throw new APIError(
        messages[response.status] ||
          `Backend request failed (HTTP ${response.status}).`,
      );
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof APIError) throw error;
    throw new APIError(
      controller.signal.aborted
        ? "Request cancelled or timed out. You can try again."
        : "Cannot reach a valid FastAPI response. Check backend connectivity and the API proxy.",
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", cancel);
  }
}
export const api = {
  locations: (signal?: AbortSignal) =>
    request<LocationRegistry>("/locations", undefined, signal),
  insights: (session_id: string, context_id: string, signal?: AbortSignal) =>
    request<InsightResponse>(
      "/environment/insights",
      { session_id, context_id },
      signal,
    ),
  measurements: (query: Query, source_mode: SourceMode, signal?: AbortSignal) =>
    request<MeasurementResponse>(
      "/environment/measurements",
      { query, source_mode },
      signal,
    ),
  selected: (
    location_ids: string[],
    start: string,
    end: string,
    session_id: string,
    source_mode: SourceMode,
    signal?: AbortSignal,
  ) =>
    request<SelectedBundle>(
      "/environment/selected",
      { location_ids, start, end, session_id, source_mode },
      signal,
    ),
  route: (
    question: string,
    session_id: string,
    language: Language | "auto",
    context_id: string | null,
    signal?: AbortSignal,
  ) =>
    request<QuestionRoute>(
      "/assistant/route",
      { question, session_id, language, context_id },
      signal,
    ),
  health: (signal?: AbortSignal) =>
    request<Health>("/health", undefined, signal),
  system: (signal?: AbortSignal) =>
    request<System>("/system", undefined, signal),
  analyze: (
    query: string,
    session_id: string,
    mode: Mode,
    signal?: AbortSignal,
  ) =>
    request<Analysis>(
      mode === "trained" ? "/nlp/analyze" : "/demo/analyze",
      { query, session_id },
      signal,
    ),
  session: (
    query: Query,
    session_id: string,
    source_mode: SourceMode,
    language: Language,
    signal?: AbortSignal,
  ) =>
    request<Bundle>(
      "/environment/session",
      { query, session_id, source_mode, language },
      signal,
    ),
  explain: (
    session_id: string,
    context_id: string,
    question: string,
    language: Language,
    signal?: AbortSignal,
  ) =>
    request<Explanation>(
      "/genai/explain",
      { session_id, context_id, question, language },
      signal,
    ),
};

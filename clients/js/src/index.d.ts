export interface AskParams {
  userId: string; message: string; llm?: string; serveThreshold?: number;
  context?: Record<string, unknown>; explain?: boolean;
  [k: string]: unknown;
}
export interface AskResponse {
  answer: string; source: 'reflex' | 'reflex+reverify' | 'llm';
  reflex_id: string | null; confidence: number; latency_ms: number;
  llm_cost_saved_inr: number; structured?: Record<string, unknown> | null;
  matched_situation?: string | null; similarity?: number | null;
  threshold?: number | null; expanded_from?: string | null;
}
export interface ClientOpts { apiKey?: string; timeoutMs?: number }
export class Client {
  constructor(baseUrl?: string, opts?: ClientOpts);
  ask(p: AskParams): Promise<AskResponse>;
  remember(userId: string, fact: string, confidence?: number): Promise<unknown>;
  reflexes(userId?: string): Promise<unknown[]>;
  feedback(reflexId: string, ok: boolean, note?: string): Promise<unknown>;
  saveReflex(p: { userId?: string; message: string; answer: string; structured?: unknown; confidence?: number }): Promise<unknown>;
  metrics(): Promise<unknown>;
  activity(limit?: number, source?: string): Promise<unknown>;
}
export function openaiChat(baseUrl: string, body: Record<string, unknown>, opts?: ClientOpts): Promise<any>;
export function anthropicMessages(baseUrl: string, body: Record<string, unknown>, opts?: ClientOpts): Promise<any>;
export default Client;

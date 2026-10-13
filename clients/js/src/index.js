// Copyright (c) 2026 Himanshu Sharma — Memflex client, Apache-2.0 (see LICENSE-CLIENT).
/**
 * memflex — thin JavaScript client for a Memflex server.
 * Zero dependencies (global fetch, Node 18+). Apache-2.0.
 *
 *   import { Client, openaiChat } from 'memflex';
 *   const rx = new Client('http://localhost:8000');
 *   const r = await rx.ask({ userId: 'u1', message: 'Where is my refund?' });
 *   // r = { answer, source: 'reflex'|'llm', confidence, latencyMs, ... }
 */
const DEFAULT_URL = (typeof process !== 'undefined' && process.env?.REFLEX_URL) || 'http://localhost:8000';

async function req(base, path, { method = 'GET', body, apiKey, timeoutMs = 60000 } = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const headers = { 'Content-Type': 'application/json' };
    const key = apiKey || (typeof process !== 'undefined' && process.env?.MEMFLEX_API_KEY) || '';
    if (key) headers['X-API-Key'] = key;
    const r = await fetch(base.replace(/\/$/, '') + path, {
      method, headers, signal: ctrl.signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`memflex ${method} ${path}: HTTP ${r.status} ${await r.text()}`.slice(0, 300));
    return r.json();
  } finally {
    clearTimeout(t);
  }
}

export class Client {
  constructor(baseUrl = DEFAULT_URL, opts = {}) {
    this.base = baseUrl;
    this.opts = opts;
  }
  ask({ userId, message, llm = 'mock/mock-echo', serveThreshold, context, explain, ...rest }) {
    return req(this.base, '/ask', { ...this.opts, method: 'POST',
      body: { user_id: userId, message, llm, serve_threshold: serveThreshold, context, explain, ...rest } });
  }
  remember(userId, fact, confidence = 0.9) {
    return req(this.base, '/remember', { ...this.opts, method: 'POST',
      body: { user_id: userId, fact, confidence } });
  }
  reflexes(userId = '') {
    return req(this.base, '/reflexes' + (userId ? `?user_id=${encodeURIComponent(userId)}` : ''), this.opts);
  }
  feedback(reflexId, ok, note = '') {
    return req(this.base, `/reflexes/${encodeURIComponent(reflexId)}/feedback`,
      { ...this.opts, method: 'POST', body: { ok, note } });
  }
  saveReflex({ userId = '', message, answer, structured, confidence = 0.9 }) {
    return req(this.base, '/reflexes', { ...this.opts, method: 'POST',
      body: { user_id: userId, message, answer, structured, confidence, source: 'explicit:js-sdk' } });
  }
  metrics() { return req(this.base, '/metrics', this.opts); }
  activity(limit = 100, source = '') {
    const q = `?limit=${limit}${source ? `&source=${encodeURIComponent(source)}` : ''}`;
    return req(this.base, '/activity' + q, this.opts);
  }
}

/** OpenAI-protocol chat via Memflex (any model string; extras ride along). */
export function openaiChat(baseUrl = DEFAULT_URL, { model, messages, user = 'js', ...rest } = {}, opts = {}) {
  return req(baseUrl, '/v1/chat/completions', { ...opts, method: 'POST',
    body: { model, messages, user: rest.user ?? user, ...rest } });
}

/** Anthropic-protocol messages via Memflex. */
export function anthropicMessages(baseUrl = DEFAULT_URL, { model, messages, max_tokens = 256, ...rest } = {}, opts = {}) {
  return req(baseUrl, '/v1/messages', { ...opts, method: 'POST',
    body: { model, messages, max_tokens, ...rest } });
}

export default Client;

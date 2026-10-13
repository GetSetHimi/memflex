// Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
// API client for the Memflex server. Base URL resolution:
// build-time NEXT_PUBLIC_REFLEX_API_URL → runtime localStorage override → localhost default.
function base() {
  if (typeof window !== 'undefined') {
    try {
      const saved = window.localStorage.getItem('mx_api');
      if (saved) return saved.replace(/\/$/, '');
    } catch {}
  }
  return (process.env.NEXT_PUBLIC_REFLEX_API_URL || 'http://localhost:8000').replace(/\/$/, '');
}

function key() {
  if (typeof window !== 'undefined') {
    try {
      const k = window.localStorage.getItem('mx_key');
      if (k) return k;
    } catch {}
  }
  return process.env.NEXT_PUBLIC_MEMFLEX_API_KEY || '';
}

async function call(path, { method = 'GET', body, timeoutMs = 60000 } = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const headers = { 'Content-Type': 'application/json' };
    const k = key();
    if (k) headers['X-API-Key'] = k;
    const r = await fetch(base() + path, {
      method, headers, signal: ctrl.signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
    return r.json();
  } finally {
    clearTimeout(t);
  }
}

export const apiBase = base;
export const getMetrics = () => call('/metrics');
export const getActivity = (limit = 100, source = '') =>
  call(`/activity?limit=${limit}${source ? `&source=${encodeURIComponent(source)}` : ''}`);
export const getReflexes = (userId = '') =>
  call('/reflexes' + (userId ? `?user_id=${encodeURIComponent(userId)}` : ''));
export const postFeedback = (id, ok) =>
  call(`/reflexes/${encodeURIComponent(id)}/feedback`, { method: 'POST', body: { ok } });
export const patchReflex = (id, patch) =>
  call(`/reflexes/${encodeURIComponent(id)}`, { method: 'PATCH', body: patch });
export const deleteReflex = (id) =>
  call(`/reflexes/${encodeURIComponent(id)}`, { method: 'DELETE' });
export const runVerify = (limit = 20) =>
  call(`/verify/run?limit=${limit}`, { method: 'POST' });
export const ping = async () => {
  try {
    await call('/health', { timeoutMs: 6000 });
    return true;
  } catch {
    return false;
  }
};

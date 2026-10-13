'use client';

import { useCallback, useEffect, useState } from 'react';
import './globals.css';
import {
  apiBase, deleteReflex, getActivity, getMetrics, getReflexes, patchReflex,
  ping, postFeedback, runVerify,
} from '../lib/api';

function reltime(iso) {
  try {
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return `${Math.floor(s)}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  } catch { return iso || '—'; }
}

const badge = (source) =>
  source === 'llm'
    ? <span className="badge llm">LLM call</span>
    : <span className="badge reflex">Reflex answer</span>;

export default function Console() {
  const [tab, setTab] = useState('overview');
  const [metrics, setMetrics] = useState(null);
  const [activity, setActivity] = useState({ items: [], llm_calls: 0, reflex_answers: 0 });
  const [memories, setMemories] = useState([]);
  const [connected, setConnected] = useState(null);
  const [apiUrl, setApiUrl] = useState('http://localhost:8000');
  const [apiKey, setApiKey] = useState('');
  const [auto, setAuto] = useState(false);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [confirmDel, setConfirmDel] = useState(null);

  const load = useCallback(async () => {
    try {
      const [m, a, r] = await Promise.all([getMetrics(), getActivity(100), getReflexes()]);
      setMetrics(m); setActivity(a); setMemories(r);
      setConnected(true); setError('');
    } catch (e) {
      setConnected(false);
      setError('Console cannot reach the API. Start it: `python3 -m reflex.api.app`. ' + String(e?.message || e));
    }
  }, []);

  useEffect(() => {
    try {
      const u = window.localStorage.getItem('mx_api');
      if (u) setApiUrl(u);
      setApiKey(window.localStorage.getItem('mx_key') || '');
    } catch {}
  }, []);

  useEffect(() => {
    ping().then(setConnected);
    load();
  }, [load]);

  useEffect(() => {
    if (!auto) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [auto, load]);

  const saveSettings = () => {
    try {
      window.localStorage.setItem('mx_api', apiUrl.replace(/\/$/, ''));
      window.localStorage.setItem('mx_key', apiKey);
    } catch {}
    setNotice('Saved — reloading from the new server.');
    setTimeout(load, 300);
  };

  const items = activity.items || [];
  const view = filter === 'llm' ? items.filter((a) => a.source === 'llm')
    : filter === 'reflex' ? items.filter((a) => a.source !== 'llm') : items;
  const mem = query
    ? memories.filter((r) => String(r.situation || '').toLowerCase().includes(query.toLowerCase()))
    : memories;

  return (
    <div className="wrap">
      <div className="topbar">
        <svg width="26" height="26" viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <rect x="2" y="2" width="28" height="28" rx="8" fill="#c8ff2e" />
          <path d="M9 21c4-1 5-8 9-9 2.4-.6 4 .8 5 2" stroke="#0c0e02" strokeWidth="2.6" strokeLinecap="round" />
          <circle cx="22.5" cy="11.5" r="2.2" fill="#0c0e02" />
        </svg>
        <span className="brand">memflex console</span>
        <span className={`dot ${connected ? 'ok' : connected === false ? 'down' : ''}`} />
        <span className="sub">{connected ? `Connected · ${apiBase()}` : connected === false ? 'API unreachable' : 'Checking…'}</span>
      </div>

      <h1>What your agent remembers vs what it pays for</h1>
      <p className="lead">Every LLM call costs money and seconds. Every reflex answer costs neither. This console proves it, live.</p>

      {error && <div className="err" style={{ marginTop: 14 }}>{error}</div>}
      {notice && <div className="card" style={{ marginTop: 14 }}>{notice}</div>}

      <div className="row" style={{ marginTop: 16 }}>
        <input className="grow" type="text" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} placeholder="API base URL" aria-label="API base URL" />
        <input type="text" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="API key (if locked)" aria-label="API key" style={{ maxWidth: 220 }} />
        <button className="btn sm" onClick={saveSettings}>Use server</button>
        <label className="sub"><input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> auto-refresh 5s</label>
        <button className="btn sm" onClick={load}>Refresh</button>
      </div>

      <div className="kpis">
        {[
          [String(metrics?.asks ?? '—'), 'Asks (lifetime)'],
          [`${((metrics?.hit_rate ?? 0) * 100).toFixed(1)}%`, 'Hit rate', true],
          [String(activity.llm_calls ?? metrics?.llm_calls ?? '—'), 'LLM calls (window)'],
          [String(activity.reflex_answers ?? '—'), 'Reflex answers (window)', true],
          [`₹${metrics?.cost_saved_30d_inr ?? 0}`, 'Saved'],
          [String(metrics?.reflex_count ?? '—'), 'Memories stored'],
          [`${activity.avg_latency_ms_llm ?? '—'} ms`, 'Avg latency — LLM'],
          [`${activity.avg_latency_ms_reflex ?? '—'} ms`, 'Avg latency — reflex'],
        ].map(([v, l, hi], i) => (
          <div className="kpi" key={i}>
            <div className="v" dangerouslySetInnerHTML={{ __html: hi ? `<em>${v}</em>` : v }} />
            <div className="l">{l}</div>
          </div>
        ))}
      </div>

      <div className="tabs">
        {[['overview', 'Overview'], ['live', 'Live activity'], ['memory', 'Memory'], ['calibration', 'Calibration']].map(([k, label]) => (
          <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="card">
          <h2>Where answers come from</h2>
          <p className="sub">LLM calls: {activity.llm_calls} · Reflex answers: {activity.reflex_answers} (recent window)</p>
          <p>New here? Ask something twice via <span className="mono">POST /ask</span> (or <span className="mono">/docs</span> → Try it out), then watch the second answer arrive from memory.</p>
        </div>
      )}

      {tab === 'live' && (
        <>
          <div className="row">
            {[['all', 'All'], ['llm', 'LLM calls'], ['reflex', 'Reflex answers']].map(([k, label]) => (
              <button key={k} className={'btn sm' + (filter === k ? ' primary' : '')} onClick={() => setFilter(k)}>{label}</button>
            ))}
            <span className="sub">{view.length} rows · newest first · reflex rows made zero LLM calls</span>
          </div>
          <div className="feed">
            {view.slice(0, 100).map((a, i) => (
              <details key={a.reflex_id + i + (a.ts || '')}>
                <summary>{badge(a.source)} <span className="sub">{a.user_id} · {String(a.message || '').slice(0, 72)} · {reltime(a.ts)}</span></summary>
                <p><b>Asked:</b> {a.message}</p>
                <p><b>Answered:</b> {a.answer}</p>
                <div className="conf"><i style={{ width: `${Math.round((a.confidence || 0) * 100)}%` }} /></div>
                <p className="sub">confidence {a.confidence} · {a.latency_ms} ms · model {a.llm_model || '—'} · saved ₹{a.llm_cost_saved_inr} · {a.reflex_id}</p>
              </details>
            ))}
            {!view.length && <p className="sub">Nothing here yet — traffic appears the moment your agent asks something.</p>}
          </div>
        </>
      )}

      {tab === 'memory' && (
        <>
          <div className="row">
            <input className="grow" type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter situations, e.g. refund" aria-label="Filter situations" />
            <button className="btn sm" onClick={async () => { try { await runVerify(20); setNotice('Verification run finished.'); load(); } catch (e) { setError(String(e?.message || e)); } }}>Re-verify stale now</button>
          </div>
          <p className="sub">{mem.length} memories · thumbs tune confidence · delete erases · TTL sets lifespan (days).</p>
          <div className="feed">
            {mem.slice(0, 100).map((r) => (
              <details key={r.id}>
                <summary>{r.confidence?.toFixed(2)} · {r.hits} hits · {r.corrections} corrections · {String(r.situation || '').slice(0, 84)}</summary>
                <p><b>Situation key:</b> <span className="mono">{r.situation}</span></p>
                <p><b>Stored answer:</b> {r.decision?.payload}</p>
                {r.decision?.structured && <pre className="mono">{JSON.stringify(r.decision.structured, null, 2)}</pre>}
                <div className="conf"><i style={{ width: `${Math.round((r.confidence || 0) * 100)}%` }} /></div>
                <p className="sub"><span className="mono">{r.id}</span> · {r.source} · TTL {r.ttl_days}d · verified {reltime(r.last_verified_at)}</p>
                <div className="row">
                  <button className="btn sm" onClick={async () => { await postFeedback(r.id, true); load(); }}>Helpful</button>
                  <button className="btn sm" onClick={async () => { await postFeedback(r.id, false); load(); }}>Wrong</button>
                  <input type="number" min="1" max="365" defaultValue={r.ttl_days || 30} id={`ttl-${r.id}`} aria-label="TTL days" style={{ maxWidth: 110 }} />
                  <button className="btn sm" onClick={async () => {
                    const el = document.getElementById(`ttl-${r.id}`);
                    await patchReflex(r.id, { ttl_days: Math.max(1, Math.min(365, parseInt(el.value || '30', 10))) });
                    load();
                  }}>Set TTL</button>
                  {confirmDel === r.id ? (
                    <>
                      <button className="btn sm danger" onClick={async () => { await deleteReflex(r.id); setConfirmDel(null); load(); }}>Yes, delete</button>
                      <button className="btn sm" onClick={() => setConfirmDel(null)}>Keep it</button>
                    </>
                  ) : (
                    <button className="btn sm danger" onClick={() => setConfirmDel(r.id)}>Delete</button>
                  )}
                </div>
              </details>
            ))}
            {!mem.length && <p className="sub">Memory is empty — memories appear after the first novel ask is distilled.</p>}
          </div>
        </>
      )}

      {tab === 'calibration' && (
        <div className="card">
          <h2>Does 0.9 confidence mean 90% right?</h2>
          <p className="sub">Estimated accuracy per band from hit consistency. Automate the high band, escalate the rest.</p>
          <table className="spec">
            <thead><tr><th>Band</th><th>Range</th><th>n</th><th>Est. accuracy</th></tr></thead>
            <tbody>
              {(metrics?.calibration || []).map((b) => (
                <tr key={b.band}><td>{b.band}</td><td>{b.range?.join(' – ')}</td><td>{b.n}</td><td>{b.est_accuracy ?? '—'}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

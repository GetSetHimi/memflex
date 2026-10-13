// memflex JS client tests — live against a local server (needs :8000 up).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Client, openaiChat, anthropicMessages } from '../src/index.js';

const BASE = process.env.REFLEX_URL || 'http://localhost:8000';
const rx = new Client(BASE);
const UID = 'js-sdk-probe';

test('ask miss then reflex hit', async () => {
  const msg = `JSPROBE where is my invoice ${Date.now()}?`;
  const r1 = await rx.ask({ userId: UID, message: msg });
  assert.equal(r1.source, 'llm');
  let r2 = {};
  for (let i = 0; i < 5; i++) {
    r2 = await rx.ask({ userId: UID, message: msg });
    if (r2.source === 'reflex') break;
  }
  assert.equal(r2.source, 'reflex');
  assert.equal(r2.answer, r1.answer);
});

test('remember + metrics + activity', async () => {
  await rx.remember(UID, 'prefers JS SDK', 0.9);
  const m = await rx.metrics();
  assert.ok(m.asks >= 2);
  const a = await rx.activity(5);
  assert.ok(a.count >= 1);
});

test('openai + anthropic compat', async () => {
  const c = await openaiChat(BASE, { model: 'mock/mock-echo',
    messages: [{ role: 'user', content: `JSCOMP ping ${Date.now()}` }], user: UID });
  assert.equal(c.object, 'chat.completion');
  assert.ok(c.choices[0].message.content.length > 0);
  const an = await anthropicMessages(BASE, { model: 'mock/mock-echo',
    messages: [{ role: 'user', content: `JSANTH ping ${Date.now()}` }] });
  assert.equal(an.type, 'message');
  assert.ok(an.content[0].text.length > 0);
});

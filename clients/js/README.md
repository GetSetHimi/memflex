# memflex (JS) — thin client for a Memflex server. Apache-2.0.

```js
import { Client } from 'memflex';
const rx = new Client('http://localhost:8000'); // or REFLEX_URL env
const r = await rx.ask({ userId: 'u1', message: 'Where is my refund?' });
// → { answer, source: 'reflex'|'llm', confidence, latency_ms, ... }
await rx.remember('u1', 'prefers COD');
```

OpenAI / Claude protocols work too (`openaiChat`, `anthropicMessages` helpers),
so any JS agent framework can point its `baseURL` at your server's `/v1`.

Test live: `npm test` (needs the API on `:8000` — `python3 -m reflex.api.app`).

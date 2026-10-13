# Launch checklist — Memflex → Product Hunt + showcase

## Name assets (locked)
- Brand: **Memflex** · domain: **memflex.dev** (buy first, ~$5 first year)
- PyPI: `memflex` · npm: `memflex` · GitHub org: `@memflex` (all verified free)
- Tagline: *"Agents call the LLM only for what they've never seen."*
- One-liner: *Reflexes + verified memory for AI agents — repeats in ~50ms at ₹0, in any language.*

## Pre-launch (code)
- [ ] `pytest` green twice, `ruff` clean, Astro + Next.js builds clean
- [ ] No secrets in repo (`grep` for keys), `.env` gitignored, live keys rotated
- [ ] LICENSE (FSL) + NOTICE + headers + CLA note live before first public push
- [ ] `docs/HOW_TO_USE.md` + site copy agree on numbers (76.7%, 0.85/0.65, 1d/30d TTLs)

## Pre-launch (assets)
- [ ] Domain live: memflex.dev → site, console subdomain → console, api subdomain → API
- [ ] 5 screenshots: (1) homepage hero, (2) /try flip (LLM→REFLEX badges),
      (3) console Live activity, (4) calibration curve, (5) Hindi + German demo
- [ ] Demo GIF (≤30s): ask → ask again → badge flips → metrics move
- [ ] Maker comment draft (first comment sets the narrative — template below)

## Maker comment template (adapt, don't paste blindly)
> Hey PH! I built Memflex because my agents kept paying full LLM price for
> questions they'd answered a thousand times. It memorizes repeats with
> calibrated confidence (76.7% served from memory in our bench), verifies
> stale memories instead of trusting them blindly, and works in 19 languages.
> Fair Source, self-hosts in 1 command. Ask me anything — especially the
> skeptical questions (there's an honest scorecard in the docs).

## Showcase order (warm → hot)
1. Friendly dev circles + AI newsletters (feedback, catch bugs)
2. Tech-influencer demos (live flip is the 10-second hook)
3. CTO/CEO intros (lead with ₹ saved math + calibration curve)
4. Product Hunt launch (Tuesday–Thursday, hunter optional but helpful)

## Day-after metrics to watch
- GitHub stars/forks, PyPI/npm downloads, /metrics hit_rate from new users,
  issues labeled `good-first-issue` conversion, competing-use inquiries
  (→ COMMERCIAL.md process).

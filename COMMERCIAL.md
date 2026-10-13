# Commercial Licensing — Memflex

Memflex's server code is **Fair Source** (FSL-1.1, see `LICENSE`):
free for nearly every use — self-host, modify, internal business use,
research, education. Each published version converts to Apache-2.0
two years after publication.

## What needs a commercial license?

A **Competing Use**: offering Memflex (or a fork) to others as a paid
agent-memory / reflex-caching service that substitutes for Memflex or
offers substantially similar functionality. If that's you, you need
a commercial agreement — running the FSL code as your SaaS without one
is a license violation.

## Process

1. Email the licensor (contact@memflex.dev) with: company, deployment
   shape (cloud/regions, tenants), expected request volume.
2. You receive countersigned commercial terms (fee + SLA tier).
3. Until signed, do not launch the competing service.

The thin client SDK (`reflex/client.py`, `reflex/plug.py`) is Apache-2.0
and never needs a commercial license — integrate freely.

## What Enterprise buys (beyond the license)

For regulated/scale teams, the commercial tier bundles the operational
surface self-host doesn't provide:

- **Runs in your cloud**: binary + Helm chart on your K8s/VPC — data never
  touches the licensor. Single-tenant by construction.
- **Identity & audit**: SSO/SAML, RBAC, immutable audit logs, custom
  retention windows, GDPR erasure runbooks.
- **Compliance paper**: DPA, SOC 2 reports, security-review support —
  the documents banks/healthcare/govt procurement require.
- **Uptime contract**: 99.99% SLA, private support channel, onboarding,
  roadmap input. Contrast Managed (hosted by us, 99.9%, shared infra).

Managed (hosted by licensor, ~₹999/mo, 10 lakh asks included) is the
zero-ops middle: same endpoints, one `base_url` change to migrate either way.

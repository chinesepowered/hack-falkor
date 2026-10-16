---
id: mtg:2026-06-18-arch-review
title: "Architecture review: webhook delivery"
date: "2026-06-18"
attendees: [person:marco, person:priya, person:hannah, person:sofia, person:jonas, person:mei]
about: [svc:webhook-dispatcher, api:webhooks, svc:event-bus, inc:INC-142]
---
# Architecture review: webhook delivery — 2026-06-18

**Attendees:** Marco Rossi, Priya Raman, Hannah Lee, Sofia Martins, Jonas Weber, Mei Tanaka

## Options
1. Synchronous retries with a longer backoff — still duplicates when a receiver times out after processing.
2. Ask customers to de-duplicate — enterprise customers like Tidewater Freight cannot change receivers this year.
3. Durable queue on the event-bus plus idempotency keys — at-least-once delivery that receivers can de-duplicate safely.

Mei confirmed the event-bus can host a dedicated delivery queue with 24h retention.

## Decisions
- Go with option 3: deliver webhooks through a durable queue with idempotency keys (ADR-007, Marco to write it up).

## Action items
- Marco: queue consumer (PLAT-402) and idempotency keys (PLAT-410).
- Mei: provision the delivery queue on the event-bus.

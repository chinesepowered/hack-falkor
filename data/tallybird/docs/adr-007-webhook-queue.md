---
id: doc:adr-007
title: "ADR-007: Webhook delivery via a durable queue"
kind: adr
authors: [person:marco]
updated: "2026-06-19"
about: [svc:webhook-dispatcher, api:webhooks, svc:event-bus]
cites: [doc:pm-142, doc:webhook-guide]
decision:
  id: dec:D-007
  title: Deliver webhooks through a durable queue with idempotency keys
  summary: webhook-dispatcher stops retrying synchronously. Every event is written to a durable queue and delivered by consumers with exponential backoff for up to 24 hours. Each event carries an Idempotency-Key header so receivers can safely ignore repeats.
  date: "2026-06-18"
  deciders: [person:marco, person:priya, person:hannah]
  meeting: mtg:2026-06-18-arch-review
  evidence: [msg:incidents-004, msg:incidents-005, msg:incidents-006, msg:platform-004]
  triggered_by: inc:INC-142
  affects: [svc:webhook-dispatcher, api:webhooks]
  implemented_by: ["pr:881", "pr:893"]
  rejected:
    - option: Synchronous retries with a longer backoff
      reason: Still delivers duplicates whenever a receiver times out after processing the event.
    - option: Ask customers to de-duplicate on their side
      reason: Tidewater Freight and other enterprise customers cannot change their receivers this year.
---
# ADR-007: Webhook delivery via a durable queue

**Status:** Accepted · **Date:** 2026-06-19 · **Deciders:** Marco Rossi, Priya Raman, Hannah Lee

## Context
During INC-142, webhook-dispatcher retried deliveries synchronously after receiver timeouts. Receivers had already processed the first attempt, so Tidewater Freight and Granite Labs booked every invoice twice for six hours. See the INC-142 postmortem.

## Decision
- webhook-dispatcher no longer retries synchronously.
- Every webhook event is written to a durable queue on the event-bus and delivered by consumers.
- Failed deliveries are retried with exponential backoff for up to 24 hours.
- Every event carries an `Idempotency-Key` header; receivers can safely ignore repeats.

## Alternatives considered
- **Synchronous retries with a longer backoff.** Rejected: still duplicates whenever a receiver times out after processing.
- **Ask customers to de-duplicate on their side.** Rejected: enterprise customers such as Tidewater Freight cannot change their receivers this year.

## Rollout
Implemented in PR #881 (queue consumer) and PR #893 (idempotency keys).

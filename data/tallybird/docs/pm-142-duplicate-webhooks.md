---
id: doc:pm-142
title: "Postmortem INC-142: Duplicate webhooks caused double invoices"
kind: postmortem
authors: [person:priya]
updated: "2026-06-12"
about: [svc:webhook-dispatcher, svc:invoicing-service, api:webhooks, inc:INC-142, cust:tidewater, cust:granite]
cites: [doc:webhook-guide]
---
# Postmortem INC-142: Duplicate webhooks caused double invoices

**Severity:** sev1 · **Date:** 2026-06-09 · **Author:** Priya Raman

## Impact
For six hours, Tidewater Freight and Granite Labs received every `invoice.created` webhook twice and booked each invoice twice.

## Root cause
webhook-dispatcher retries synchronously when a receiver does not answer within 10 seconds. Tidewater's receiver processed the first attempt but answered slowly, so the retry created a duplicate. Events carried no idempotency key, so receivers could not tell repeats apart.

## What went well
Wei Zhang spotted the pattern from two support tickets within 20 minutes.

## Action items
- Replace synchronous retries with a durable queue (see ADR-007). Owner: Marco Rossi.
- Add an idempotency key to every webhook event. Owner: Marco Rossi.
- Credit affected invoices for Tidewater Freight and Granite Labs. Owner: Diego Alvarez.

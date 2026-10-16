---
id: doc:adr-011
title: "ADR-011: OAuth 2.0 for API v2, deprecate v1 API keys"
kind: adr
authors: [person:olivia, person:marco]
updated: "2026-05-05"
about: [api:rest-v1, api:rest-v2, svc:auth-service, svc:public-api-gateway]
decision:
  id: dec:D-011
  title: REST API v2 is OAuth-only; v1 API keys are deprecated with no sunset date yet
  summary: REST API v2 authenticates with OAuth 2.0 client credentials only. REST API v1 and its API keys are deprecated but keep working; no sunset date is set, and customers get at least 60 days notice before one is.
  date: "2026-05-04"
  deciders: [person:olivia, person:marco, person:hannah]
  meeting: mtg:2026-05-04-api-v2-review
  evidence: [msg:platform-001, msg:platform-003]
  affects: [api:rest-v1, api:rest-v2, svc:auth-service, svc:public-api-gateway]
  implemented_by: ["pr:902", "pr:915"]
  rejected:
    - option: Keep long-lived API keys in v2
      reason: Keys leak through logs and support tickets; we cannot scope or expire them.
    - option: Mutual TLS for every client
      reason: Too much setup for small customers; support load would explode.
---
# ADR-011: OAuth 2.0 for API v2, deprecate v1 API keys

**Status:** Accepted · **Date:** 2026-05-05 · **Deciders:** Olivia Grant, Marco Rossi, Hannah Lee

## Context
REST API v1 authenticates with long-lived API keys in the `X-Api-Key` header. Keys leak into logs and support tickets, and we cannot scope them.

## Decision
- REST API v2 accepts OAuth 2.0 client credentials only; auth-service issues short-lived tokens.
- REST API v1 and v1 API keys are **deprecated** but keep working.
- No sunset date is set yet. Customers will get at least 60 days notice before v1 is switched off.

## Alternatives considered
- **Keep long-lived API keys in v2.** Rejected: cannot scope or expire them.
- **Mutual TLS for every client.** Rejected: too much setup for small customers.

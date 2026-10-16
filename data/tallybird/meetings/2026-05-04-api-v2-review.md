---
id: mtg:2026-05-04-api-v2-review
title: API v2 auth design review
date: "2026-05-04"
attendees: [person:olivia, person:marco, person:hannah, person:kenji, person:dana, person:jonas]
about: [api:rest-v1, api:rest-v2, svc:auth-service, svc:public-api-gateway]
---
# API v2 auth design review — 2026-05-04

**Attendees:** Olivia Grant, Marco Rossi, Hannah Lee, Kenji Sato, Dana Okafor, Jonas Weber

## Notes
- Olivia presented OAuth 2.0 client credentials for REST API v2.
- Dana explained how the v1 API key validator in auth-service works; it is fragile and only she has changed it in two years.
- Kenji worried about the SDKs: the Python SDK still defaults to v1.
- Hannah asked for no sunset date until we know how many customers are left on v1.
- Mutual TLS was rejected as too heavy for small customers.

## Decisions
- REST API v2 is OAuth-only; v1 API keys are deprecated with no sunset date yet (ADR-011).

## Action items
- Olivia + Marco: write ADR-011.
- Kenji: write the OAuth migration guide.
- Jonas: plan deprecation headers on v1 responses.

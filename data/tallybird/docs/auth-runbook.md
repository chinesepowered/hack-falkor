---
id: doc:auth-runbook
title: auth-service runbook
kind: runbook
authors: [person:dana]
updated: "2026-05-20"
about: [svc:auth-service, api:rest-v1, api:rest-v2]
cites: [doc:adr-011]
---
# auth-service runbook

## What it does
auth-service validates v1 API keys for the public-api-gateway and issues OAuth 2.0 access tokens for REST API v2.

## v1 API key validator
- Key lookups are cached for 10 minutes; a rolled key can take that long to be rejected.
- Keys are compared in constant time against an HMAC of the stored secret.
- Escalation: page Dana Okafor for any key validator issue. Nobody else has worked on the validator.

## OAuth token endpoint
- Tokens live for 1 hour and are signed with keys rotated weekly.
- If p99 latency on `/oauth/token` exceeds 1s, warm the signing-key cache (see INC-151).

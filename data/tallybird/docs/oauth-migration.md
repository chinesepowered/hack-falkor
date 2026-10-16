---
id: doc:oauth-migration
title: "Migrating from v1 API keys to OAuth (API v2)"
kind: guide
authors: [person:olivia, person:kenji]
updated: "2026-05-20"
about: [api:rest-v1, api:rest-v2, svc:auth-service]
cites: [doc:adr-011, doc:api-quickstart]
---
# Migrating from v1 API keys to OAuth (API v2)

REST API v2 uses OAuth 2.0 client credentials instead of API keys.

## Steps
1. Create OAuth client credentials in the dashboard under **Settings → OAuth clients**.
2. Exchange them for an access token at `POST /oauth/token`.
3. Send the token as `Authorization: Bearer <token>` to `https://api.tallybird.example/v2`.

## Timeline
v1 API keys keep working. No sunset date has been set yet, and we will give every customer at least 60 days notice before v1 is switched off.

## SDKs
The Node SDK uses v2 by default. The Python SDK needs `api_version="v2"`.

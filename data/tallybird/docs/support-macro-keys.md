---
id: doc:support-macro-keys
title: "Support macro: Rotating an API key"
kind: macro
authors: [person:wei]
updated: "2026-04-02"
about: [api:rest-v1, svc:auth-service]
cites: [doc:api-quickstart]
---
# Support macro: Rotating an API key

Hi {{customer_name}},

You can rotate your API key yourself under **Settings → API keys → Roll key** in the dashboard. Your old v1 API key keeps working for 24 hours, so you have time to deploy the new one. Send the new key in the `X-Api-Key` header exactly as before.

If you see `401 invalid_api_key` after rotating, the key validator cache can take up to 10 minutes to pick up the change.

Best,
Tallybird Support

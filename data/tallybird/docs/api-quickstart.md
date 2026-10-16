---
id: doc:api-quickstart
title: API Quickstart
kind: guide
authors: [person:kenji]
updated: "2026-03-02"
about: [api:rest-v1, api:webhooks, svc:public-api-gateway]
cites: [doc:webhook-guide]
---
# API Quickstart

Welcome to Tallybird! This guide gets you from zero to your first invoice in five minutes.

## 1. Authenticate
Every request is authenticated with your secret API key, sent in the `X-Api-Key` header. Create a key in the dashboard under **Settings → API keys**.

## 2. Make your first call
The base URL is `https://api.tallybird.example/v1`. Create an invoice with `POST /v1/invoices`:

```bash
curl https://api.tallybird.example/v1/invoices \
  -H "X-Api-Key: $TALLYBIRD_API_KEY" \
  -d customer=cus_123 -d amount=4200 -d currency=eur
```

## 3. Listen for webhooks
Register an endpoint to receive `invoice.created` and `invoice.paid` events. If your endpoint fails, we retry the delivery synchronously up to 3 times, 5 seconds apart. See the Webhook integration guide for signatures.

## 4. Go live
Rotate your test API key for a live API key before launch. Keys never expire, so store them in a secrets manager.

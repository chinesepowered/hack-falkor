---
id: doc:webhook-guide
title: Webhook integration guide
kind: guide
authors: [person:marco]
updated: "2026-02-10"
about: [api:webhooks, svc:webhook-dispatcher]
---
# Webhook integration guide

Tallybird sends webhook events such as `invoice.created`, `invoice.paid` and `payout.sent` to your HTTPS endpoint.

## Delivery and retries
Your endpoint must answer with a 2xx status within 10 seconds. Failed deliveries are retried synchronously three times with a 5 second backoff, then dropped.

## Verifying signatures
Every request carries an `X-Tallybird-Signature` header: an HMAC-SHA256 of the raw body with your webhook secret. Reject requests whose signature does not match.

## Ordering
Events can arrive out of order. Use the `created_at` field, not arrival time.

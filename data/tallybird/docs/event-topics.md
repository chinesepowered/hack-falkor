---
id: doc:event-topics
title: Event bus topics catalog
kind: spec
authors: [person:felix]
updated: "2025-12-01"
about: [svc:event-bus, svc:usage-metering, svc:webhook-dispatcher]
---
# Event bus topics catalog

| Topic | Producer | Main consumers |
|---|---|---|
| `invoice.created` | invoicing-service | webhook-dispatcher, analytics-pipeline |
| `payment.captured` | payments-core | ledger-service, webhook-dispatcher |
| `usage.recorded` | public-api-gateway | usage-metering |
| `payout.sent` | payouts | webhook-dispatcher, notification-service |

Topics are retained for 7 days. Schemas live in the `event-schemas` repo.

---
id: doc:data-retention
title: Data retention policy
kind: policy
authors: [person:sam]
updated: "2026-02-01"
about: [svc:analytics-pipeline, svc:event-bus]
---
# Data retention policy

- Raw events on the event-bus are kept for 7 days.
- The analytics warehouse keeps aggregated data for 3 years.
- Invoices and ledger entries are kept for 10 years to meet accounting rules.
- Support tickets are anonymised after 2 years.

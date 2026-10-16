---
id: doc:ubb-onepager
title: "Usage-based billing pilot: one-pager"
kind: onepager
authors: [person:chloe]
updated: "2026-07-23"
about: [svc:usage-metering, svc:invoicing-service, svc:billing-portal, cust:saltmarsh, cust:copperleaf]
cites: [doc:event-topics]
decision:
  id: dec:D-012
  title: Run the usage-based billing pilot as one cross-team squad
  summary: Growth, Data and Payments run the usage-based billing (UBB) pilot as a single squad with its own channel and weekly sync, instead of three separate team backlogs. Pilot customers are Saltmarsh Analytics and Copperleaf Media.
  date: "2026-07-22"
  deciders: [person:chloe, person:rafael, person:sofia, person:hannah]
  meeting: mtg:2026-07-22-ubb-kickoff
  evidence: [msg:ubb-001]
  affects: [svc:usage-metering, svc:invoicing-service, svc:billing-portal]
  rejected:
    - option: Each team builds its part from its own backlog
      reason: The last cross-team billing project slipped two quarters on hand-offs.
---
# Usage-based billing pilot: one-pager

**Owner:** Chloe Dubois · **Squad:** Chloe Dubois, Rafael Silva, Sofia Martins, Omar Farouk, Maya Cohen

## Why
Customers want to pay for what they use. Saltmarsh Analytics and Copperleaf Media agreed to pilot usage-based billing (UBB) in Q4.

## How
- usage-metering aggregates `usage.recorded` events per customer per day.
- invoicing-service turns daily usage into invoice line items.
- billing-portal shows live usage and projected invoices.

## Working agreement
One squad, one channel (#ubb-pilot), one weekly sync. No hand-offs between team backlogs.

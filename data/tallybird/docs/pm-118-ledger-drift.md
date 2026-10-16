---
id: doc:pm-118
title: "Postmortem INC-118: Ledger reconciliation drift"
kind: postmortem
authors: [person:dana]
updated: "2026-03-18"
about: [svc:ledger-service, inc:INC-118]
cites: [doc:adr-003]
---
# Postmortem INC-118: Ledger reconciliation drift

**Severity:** sev2 · **Date:** 2026-03-14 · **Author:** Dana Okafor

## What happened
The nightly reconciliation in ledger-service reported a 0.4% drift against payments-core. Late usage events from the event-bus were posted twice after a consumer restart.

## Resolution
Dana replayed the affected day with `ledger-cli reconcile --date 2026-03-13` and added a drift alert at 0.01%.

## Follow-ups
- Make ledger posting idempotent per event id (PAY-221, done).
- Document the replay procedure in the ledger-service runbook.

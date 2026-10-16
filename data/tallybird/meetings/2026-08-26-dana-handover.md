---
id: mtg:2026-08-26-dana-handover
title: "Dana's handover: ledger-service"
date: "2026-08-26"
attendees: [person:dana, person:tom, person:wei, person:sofia]
about: [svc:ledger-service, svc:auth-service]
---
# Dana's handover: ledger-service — 2026-08-26

**Attendees:** Dana Okafor, Tom Becker, Wei Zhang, Sofia Martins

## Covered
- Nightly reconciliation and how to replay a day with `ledger-cli reconcile`.
- Why the ledger uses banker's rounding (ADR-003) and what breaks if you change it.
- Drift alert thresholds.

## Not covered (ran out of time)
- auth-service and the v1 API key validator. Dana: "Marco reviewed some of it, ask him."
- Multi-currency design for PAY-240.

## Follow-ups
- Tom: find a new owner for ledger-service and auth-service. (No owner assigned yet.)

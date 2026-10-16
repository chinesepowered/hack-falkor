---
id: doc:ledger-runbook
title: ledger-service runbook
kind: runbook
authors: [person:dana]
updated: "2026-07-30"
about: [svc:ledger-service]
cites: [doc:adr-003, doc:pm-118]
---
# ledger-service runbook

## Nightly reconciliation
Reconciliation runs every night at 02:00 UTC and compares ledger-service with payments-core.

## Drift alert
If drift exceeds 0.01%, page Dana Okafor. Do not edit ledger rows by hand.

## Replaying a day
Re-run reconciliation for a single day with `ledger-cli reconcile --date YYYY-MM-DD`. Replays are idempotent per event id since PAY-221.

## Rounding
The ledger uses banker's rounding (ADR-003). Changing it breaks reconciliation with payments-core.

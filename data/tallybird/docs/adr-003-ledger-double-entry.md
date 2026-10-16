---
id: doc:adr-003
title: "ADR-003: Double-entry ledger with nightly reconciliation"
kind: adr
authors: [person:dana]
updated: "2025-11-06"
about: [svc:ledger-service, svc:payments-core, svc:payouts]
decision:
  id: dec:D-003
  title: Ledger is double-entry and reconciles nightly at 02:00 UTC
  summary: Every balance movement in ledger-service is written as a balanced pair of entries. A reconciliation job compares the ledger with payments-core every night at 02:00 UTC. Amounts use banker's rounding.
  date: "2025-11-05"
  deciders: [person:dana, person:priya]
  meeting: mtg:2025-11-05-ledger-review
  evidence: [msg:payments-002]
  affects: [svc:ledger-service, svc:payments-core, svc:payouts]
  rejected:
    - option: Single-entry balances updated in place
      reason: Impossible to audit after a partial failure; no way to prove where money went.
    - option: Real-time reconciliation on every write
      reason: Doubles write latency on the payments hot path for little benefit.
---
# ADR-003: Double-entry ledger with nightly reconciliation

**Status:** Accepted · **Date:** 2025-11-06 · **Deciders:** Dana Okafor, Priya Raman

## Context
payments-core and payouts both need a trustworthy record of every balance movement. Today balances are updated in place, and when a refund fails halfway we cannot prove what happened.

## Decision
- ledger-service records every movement as a balanced pair of debit and credit entries.
- A reconciliation job compares the ledger with payments-core every night at 02:00 UTC.
- All amounts use banker's rounding (round half to even) to avoid systematic drift.
- Ledger balances are eventually consistent; they can lag payments-core by up to a day.

## Alternatives considered
- **Single-entry balances updated in place.** Rejected: impossible to audit after a partial failure.
- **Real-time reconciliation on every write.** Rejected: doubles write latency on the payments hot path.

## Consequences
payouts must read settled balances from ledger-service, never from payments-core directly.

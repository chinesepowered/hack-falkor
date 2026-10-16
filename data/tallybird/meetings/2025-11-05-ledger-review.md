---
id: mtg:2025-11-05-ledger-review
title: Ledger design review
date: "2025-11-05"
attendees: [person:dana, person:priya, person:sofia, person:marco, person:tom]
about: [svc:ledger-service, svc:payments-core]
---
# Ledger design review — 2025-11-05

**Attendees:** Dana Okafor, Priya Raman, Sofia Martins, Marco Rossi, Tom Becker

## Notes
- Dana walked through the double-entry model for ledger-service. Every movement is a balanced debit/credit pair.
- Priya asked whether payouts can read from payments-core directly. Answer: no, payouts must read settled balances from the ledger.
- Marco pushed for banker's rounding after the 2024 rounding bug; agreed.
- Real-time reconciliation was discussed and rejected because of hot-path latency.

## Decisions
- Adopt the double-entry ledger with nightly reconciliation at 02:00 UTC (written up as ADR-003 by Dana).

## Action items
- Dana: write ADR-003.
- Sofia: switch invoicing-service to read balances from ledger-service.

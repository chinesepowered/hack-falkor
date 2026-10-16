---
id: doc:payouts-spec
title: Payout scheduling spec
kind: spec
authors: [person:liam]
updated: "2026-04-11"
about: [svc:payouts, svc:ledger-service]
cites: [doc:adr-003]
---
# Payout scheduling spec

payouts runs daily at 06:00 UTC and pays out settled balances on a T+2 schedule. Balances are read from ledger-service after the nightly reconciliation finishes. Payouts above 50,000 EUR need a second approver in the admin console.

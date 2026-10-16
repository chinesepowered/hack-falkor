---
id: doc:oncall-handbook
title: On-call handbook
kind: handbook
authors: [person:arjun, person:hannah]
updated: "2026-06-30"
about: [svc:ledger-service, svc:auth-service, svc:webhook-dispatcher, svc:public-api-gateway, svc:payments-core]
cites: [doc:ledger-runbook, doc:auth-runbook]
---
# On-call handbook

## Rotations
Platform and Payments each run a weekly rotation. Hand-offs happen Mondays at 10:00.

## Escalation table
| Service | Escalate to |
|---|---|
| public-api-gateway | Jonas Weber |
| auth-service | Dana Okafor |
| webhook-dispatcher | Marco Rossi |
| payments-core | Priya Raman |
| ledger-service | Dana Okafor |

## Severity
- sev1: customer money is wrong or webhooks are failing for everyone. Page immediately.
- sev2: degraded service for some customers. Page during business hours.

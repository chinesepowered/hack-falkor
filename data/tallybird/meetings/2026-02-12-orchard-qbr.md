---
id: mtg:2026-02-12-orchard-qbr
title: Orchard Health quarterly business review
date: "2026-02-12"
attendees: [person:aisha, person:emma, person:olivia]
about: [cust:orchard, api:rest-v1]
decision:
  id: dec:D-009
  title: Keep REST API v1 working for Orchard Health through 2027
  summary: Orchard Health has a regulatory freeze on integration changes until January 2028. Sales committed that their REST API v1 integration with API keys keeps working through the end of 2027.
  date: "2026-02-12"
  deciders: [person:aisha, person:olivia]
  evidence: [msg:sales-001, msg:sales-002, msg:sales-007]
  affects: [api:rest-v1, cust:orchard]
---
# Orchard Health QBR — 2026-02-12

**Attendees:** Aisha Bello, Emma Nakamura, Olivia Grant (Tallybird); Orchard's head of finance systems

## Notes
- Orchard Health renewed for two years (420k ARR). Their integration runs on REST API v1 with API keys.
- Orchard is under a regulatory change freeze for patient billing systems until January 2028; they cannot touch their integration before then.
- Olivia previewed the OAuth plans for API v2. Orchard asked for a written guarantee on v1.

## Decisions
- Aisha committed that Orchard Health's REST API v1 integration keeps working through the end of 2027. Emma will add the commitment to the contract notes.

## Action items
- Emma: record the v1 commitment in the CRM and contract notes.
- Olivia: make sure the API v2 plan accounts for Orchard.

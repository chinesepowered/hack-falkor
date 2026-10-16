"""Generate deterministic background activity for the fictional Tallybird dataset.

The hand-written files (slack.yaml, tickets.yaml, prs.yaml, docs/, meetings/) carry
the demo storylines. This script adds routine, low-signal work (PRs, tickets and
chatter inside each team) so the collaboration graph has realistic team structure.
Output: data/tallybird/generated.yaml (committed, so seeding never needs this script).
"""
import random
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1] / "data" / "tallybird"
rng = random.Random(1729)

TEAMS = {
    "platform": {
        "engineers": ["marco", "jonas", "mei", "arjun"],
        "others": ["ines", "olivia"],
        "services": ["public-api-gateway", "webhook-dispatcher", "event-bus", "notification-service"],
        "prefix": "PLAT", "channel": "platform", "prs": 9, "tickets": 5,
        "pr_titles": ["Add p99 latency dashboard for {svc}", "Fix flaky integration test in {svc}",
                      "Structured logging in {svc}", "Per-customer rate limit config in {svc}",
                      "Rotate TLS certificates for {svc}", "Reduce cold start time of {svc}",
                      "Alert on consumer lag in {svc}", "Bump dependencies in {svc}"],
        "ticket_titles": ["{svc}: noisy alert during deploys", "{svc}: document config flags",
                          "{svc}: memory creep after 7 days uptime", "{svc}: add canary stage"],
        "chatter": ["Deploying {svc} {ver} to production.", "Anyone else seeing flaky tests in {svc}?",
                    "{svc} p99 is back to normal after the config change.", "Can someone review my {svc} PR today?"],
        "replies": ["On it.", "Looks good to me.", "Seen it too, I'll take a look after standup.", "Done, approved."],
    },
    "payments": {
        "engineers": ["priya", "sofia", "liam", "nadia"],
        "others": ["tom"],
        "services": ["payments-core", "payouts", "invoicing-service"],
        "prefix": "PAY", "channel": "payments", "prs": 7, "tickets": 4,
        "pr_titles": ["Handle partial refunds in {svc}", "Currency formatting fix in {svc}",
                      "Settlement report export from {svc}", "Retry failed captures in {svc}",
                      "Payout batch size limit in {svc}", "Audit log for manual adjustments in {svc}"],
        "ticket_titles": ["{svc}: rounding difference on CHF invoices", "{svc}: slow settlement export",
                          "{svc}: support SEPA instant", "{svc}: clearer error for expired cards"],
        "chatter": ["Settlement numbers for {month} look clean.", "Edge case in {svc}: refunds across two currencies.",
                    "{svc} deploy is done, watching the error rate.", "Who has context on {svc} retries?"],
        "replies": ["Thanks!", "I can pair on it tomorrow.", "Added a test for it.", "Nice catch."],
    },
    "data": {
        "engineers": ["rafael", "yuki", "ana"],
        "others": ["ben"],
        "services": ["analytics-pipeline", "usage-metering"],
        "prefix": "DATA", "channel": "data", "prs": 5, "tickets": 3,
        "pr_titles": ["Partition {svc} tables by month", "Backfill job for {svc}", "Schema migration for {svc}",
                      "Data quality checks in {svc}"],
        "ticket_titles": ["{svc}: late partitions on Mondays", "{svc}: dedupe customer dimension",
                          "{svc}: cost report"],
        "chatter": ["{svc} backfill for {month} finished.", "Warehouse costs dropped after the {svc} change.",
                    "Heads up: {svc} schema change lands tomorrow."],
        "replies": ["Thanks for the heads up.", "Dashboard refreshed.", "Looks right to me."],
    },
    "growth": {
        "engineers": ["omar", "zoe"],
        "others": ["chloe", "maya"],
        "services": ["billing-portal", "onboarding-flow"],
        "prefix": "GROW", "channel": "growth", "prs": 5, "tickets": 3,
        "pr_titles": ["A/B test for signup copy in {svc}", "Accessibility fixes in {svc}", "Dark mode for {svc}",
                      "Better form validation in {svc}"],
        "ticket_titles": ["{svc}: confusing empty state", "{svc}: mobile layout breaks under 360px",
                          "{svc}: add product tour"],
        "chatter": ["New {svc} build is on staging.", "Conversion on {svc} is up this week.",
                    "Design review for {svc} on Thursday."],
        "replies": ["Love it.", "I'll take a look.", "Shipping it."],
    },
    "devrel": {
        "engineers": ["kenji", "elena"],
        "others": [],
        "services": ["python-sdk", "node-sdk"],
        "prefix": "DEVREL", "channel": "eng", "prs": 3, "tickets": 2,
        "pr_titles": ["Typed responses in {svc}", "More docs examples for {svc}", "Changelog automation for {svc}"],
        "ticket_titles": ["{svc}: publish to package registry from CI", "{svc}: examples for refunds"],
        "chatter": ["{svc} {ver} is released.", "New examples for {svc} are in the docs."],
        "replies": ["Nice!", "Thanks Kenji."],
    },
}
SUPPORT = ["wei", "rosa", "kofi"]
SALES = ["aisha", "lucas", "emma", "diego"]
CUSTOMERS = ["bluefin", "orchard", "nimbus", "copperleaf", "granite", "pinecrest", "brightwater",
             "saltmarsh", "tidewater", "harborview", "kestrel", "larkspur"]
CUSTOMER_NAMES = {
    "bluefin": "Bluefin Logistics", "orchard": "Orchard Health", "nimbus": "Nimbus Retail",
    "copperleaf": "Copperleaf Media", "granite": "Granite Labs", "pinecrest": "Pinecrest Clinics",
    "brightwater": "Brightwater Schools", "saltmarsh": "Saltmarsh Analytics", "tidewater": "Tidewater Freight",
    "harborview": "Harborview Travel", "kestrel": "Kestrel Outdoor", "larkspur": "Larkspur Foods",
}
MONTHS = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
          "2026-07", "2026-08", "2026-09", "2026-10"]


def day(month: str) -> str:
    if month == "2026-10":
        return f"{month}-{rng.randint(1, 14):02d}"
    return f"{month}-{rng.randint(1, 28):02d}"


def main() -> None:
    prs, tickets, messages = [], [], []
    pr_no, ticket_no = 700, {}
    for team, cfg in TEAMS.items():
        for _ in range(cfg["prs"]):
            pr_no += 1
            svc = rng.choice(cfg["services"])
            author = rng.choice(cfg["engineers"])
            pool = [p for p in cfg["engineers"] if p != author]
            reviewers = rng.sample(pool, k=min(len(pool), rng.choice([1, 1, 2])))
            prs.append({
                "number": pr_no, "repo": svc, "title": rng.choice(cfg["pr_titles"]).format(svc=svc),
                "author": f"person:{author}", "reviewers": [f"person:{r}" for r in reviewers],
                "services": [f"svc:{svc}"], "merged": day(rng.choice(MONTHS)), "body": "Routine change.",
            })
        for _ in range(cfg["tickets"]):
            n = ticket_no.get(cfg["prefix"], 600) + 1
            ticket_no[cfg["prefix"]] = n
            svc = rng.choice(cfg["services"])
            created = day(rng.choice(MONTHS))
            status = rng.choice(["done", "done", "in_progress", "open"])
            t = {
                "key": f"{cfg['prefix']}-{n}", "title": rng.choice(cfg["ticket_titles"]).format(svc=svc),
                "status": status, "priority": rng.choice(["low", "medium", "medium", "high"]),
                "reporter": f"person:{rng.choice(cfg['engineers'] + cfg['others'])}",
                "assignee": f"person:{rng.choice(cfg['engineers'])}", "created": created,
                "services": [f"svc:{svc}"], "description": "Routine work item.",
            }
            if status == "done":
                t["resolved"] = created
            tickets.append(t)
        members = cfg["engineers"] + cfg["others"]
        for i in range(6):
            svc = rng.choice(cfg["services"])
            month = rng.choice(MONTHS)
            root_id = f"msg:gen-{team}-{i:03d}"
            messages.append({
                "id": root_id, "channel": f"chan:{cfg['channel']}", "author": f"person:{rng.choice(members)}",
                "ts": f"{day(month)}T{rng.randint(8, 17):02d}:{rng.randint(0, 59):02d}:00Z",
                "text": rng.choice(cfg["chatter"]).format(svc=svc, ver=f"v{rng.randint(1, 9)}.{rng.randint(0, 20)}", month=month),
            })
            for j in range(rng.choice([1, 1, 2])):
                messages.append({
                    "id": f"{root_id}-r{j}", "channel": f"chan:{cfg['channel']}", "reply_to": root_id,
                    "author": f"person:{rng.choice(members)}",
                    "ts": f"{messages[-1]['ts'][:11]}{rng.randint(18, 20):02d}:{rng.randint(0, 59):02d}:00Z",
                    "text": rng.choice(cfg["replies"]),
                })
    # support tickets reported for customers (no v1 mentions: the integration facts live in CRM data)
    support_titles = ["{cust}: invoice PDF missing logo", "{cust}: question about payout timing",
                      "{cust}: wants CSV export of invoices", "{cust}: dashboard login loop",
                      "{cust}: tax ID not shown on invoice"]
    for _ in range(8):
        n = ticket_no.get("SUP", 400) + 1
        ticket_no["SUP"] = n
        cust = rng.choice(CUSTOMERS)
        created = day(rng.choice(MONTHS))
        tickets.append({
            "key": f"SUP-{n}", "title": rng.choice(support_titles).format(cust=CUSTOMER_NAMES[cust]),
            "status": "done", "priority": "low", "reporter": f"person:{rng.choice(SUPPORT)}",
            "assignee": f"person:{rng.choice(SUPPORT)}", "created": created, "resolved": created,
            "customers": [f"cust:{cust}"], "description": "Customer request handled by support.",
        })
    support_chatter = ["Ticket queue is clear for today.", "New macro for invoice PDF questions is live.",
                       "Can someone cover the afternoon queue?"]
    sales_chatter = ["Pipeline review moved to Thursday.", "Renewal call with {cust} went well.",
                     "{cust} asked for a reference customer in their industry."]
    for i in range(4):
        messages.append({"id": f"msg:gen-support-{i:03d}", "channel": "chan:support",
                         "author": f"person:{rng.choice(SUPPORT)}",
                         "ts": f"{day(rng.choice(MONTHS))}T{rng.randint(8, 17):02d}:00:00Z",
                         "text": rng.choice(support_chatter)})
        messages.append({"id": f"msg:gen-sales-{i:03d}", "channel": "chan:sales",
                         "author": f"person:{rng.choice(SALES)}",
                         "ts": f"{day(rng.choice(MONTHS))}T{rng.randint(8, 17):02d}:00:00Z",
                         "text": rng.choice(sales_chatter).format(cust=CUSTOMER_NAMES[rng.choice(CUSTOMERS)])})
    out = {"prs": prs, "tickets": tickets, "messages": messages}
    header = "# GENERATED by scripts/generate_filler.py (seed 1729). Routine background activity.\n"
    (ROOT / "generated.yaml").write_text(header + yaml.safe_dump(out, sort_keys=False, allow_unicode=True))
    print(f"wrote {len(prs)} PRs, {len(tickets)} tickets, {len(messages)} messages")


if __name__ == "__main__":
    main()

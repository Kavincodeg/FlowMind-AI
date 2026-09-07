# Team Routing Policy

## Purpose
This policy defines which support team is responsible for handling tickets based on issue category, and the routing rules for escalated tickets.

## Standard Routing (Tier 1)

| Issue Category | Primary Team | Escalation Team |
|---|---|---|
| billing | Billing Team | Finance & Compliance Team |
| delivery | Logistics Team | Operations Manager |
| product_defect | Quality Team | Engineering Team |
| account_access | IT Support Team | Security Team |
| service_quality | Customer Success Team | People & Culture Team |

## Routing Rules

1. **Primary assignment** is based on `issue_category` at ticket creation.
2. If the issue spans multiple categories (e.g. billing + account access), assign to the category matching the primary complaint. Document the secondary category in the ticket.
3. **Re-routing** is permitted only with supervisor approval and must be logged.

## Escalation Routing

When a ticket is escalated:
- L1 Escalation: Route to Senior Agent within the same team.
- L2 Escalation: Route to Team Manager of the primary team.
- L3 Escalation: Route to Department Head — requires notification to Customer Success Director.
- L4 Escalation: Executive Team — requires VP Customer Experience sign-off.

### Special Cases

- **Billing disputes > $1000**: Automatically route to Finance & Compliance Team (not Billing Team) after L1 escalation.
- **Security-related account issues**: Route to Security Team immediately, bypass standard Tier 1.
- **Legal/regulatory threats**: Route to Legal & Compliance Team in parallel with standard escalation.
- **Repeat complainers (5+ tickets in 90 days)**: Flag for Customer Success Director review.

## Cross-Team Collaboration

Teams may request involvement from another team via internal ticket notes. The receiving team must acknowledge within their standard SLA. Ownership remains with the primary assigned team unless formally transferred with both team manager approvals.

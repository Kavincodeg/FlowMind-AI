# Escalation Policy

## Purpose
This policy defines the criteria and process for escalating customer complaints to the appropriate team when standard support cannot resolve the issue within agreed SLA boundaries.

## Escalation Triggers

A ticket MUST be escalated when ANY of the following conditions are met:

1. **SLA Breach** — the ticket has exceeded its SLA deadline without resolution.
2. **Repeat Contact** — the same customer has opened 3 or more tickets for the same issue category within 30 days.
3. **High Priority Open** — a ticket is marked `priority=high` and remains `status=open` for more than 24 hours.
4. **Customer Threat** — the customer has explicitly threatened legal action, social media exposure, or regulatory complaint.
5. **Manager Request** — the handling agent flags the ticket for supervisor review.
6. **Financial Impact** — the issue involves a disputed amount greater than $500 or affects more than 5 customer accounts simultaneously.

## Escalation Levels

| Level | Description | Response Time |
|---|---|---|
| L1 | Senior Support Agent | Within 4 hours |
| L2 | Team Manager | Within 2 hours |
| L3 | Department Head | Within 1 hour |
| L4 | Executive Team | Immediate |

High-priority tickets with SLA breach go directly to L2. Repeat offenders (4+ tickets) go to L2. Legal threats go to L3.

## Escalation Process

1. Agent identifies escalation trigger.
2. Agent documents reason in the ticket history note.
3. System (or agent) routes to the appropriate team using the Team Routing Policy.
4. Escalation is logged with: timestamp, trigger reason, agent ID, target team, approval status.
5. Customer is notified of escalation within 30 minutes.
6. Escalated ticket must be acknowledged by receiving team within the Level response time.

## Prohibited Actions

- Agents MUST NOT close a ticket without resolution if an escalation trigger is active.
- Escalation decisions CANNOT be reversed without L2 approval.
- No ticket may be escalated and de-escalated more than twice.

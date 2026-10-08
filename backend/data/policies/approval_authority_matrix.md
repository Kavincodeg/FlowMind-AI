# Approval Authority Matrix

## Document Control

| Field | Value |
|---|---|
| Version | 1.0 |
| Effective date | 2026-10-08 |
| Owner | Head of Support |
| Review cycle | Every 6 months |

## Purpose

This document states exactly who may approve each action. It is the single source of truth for approval authority. The FlowMind system enforces it. An AI recommendation is never an approval.

## Roles

| Role | System role name | Escalation level owned |
|---|---|---|
| Tier 1 Agent | support_agent | none |
| Team Lead | team_lead | L1 |
| Team Manager | team_manager | L2 |
| Department Head | department_head | L3 |
| Executive | executive | L4 |
| Finance Reviewer | finance_reviewer | none |
| VP Finance | vp_finance | none |
| System Administrator | system_admin | none |

## Who Can Approve What

| Role | May approve |
|---|---|
| Tier 1 Agent | Standard resolutions. Refunds up to $50 |
| Team Lead | Everything a Tier 1 Agent can. Re-routing within the team. L1 escalations. Refunds up to $200. Closing a case without resolution when the customer is unreachable |
| Team Manager | Everything a Team Lead can. L2 escalations. Accepting or releasing a cross-team transfer. Refunds up to $500. Reversing an escalation. Restricting an abusive customer to email |
| Department Head | Everything a Team Manager can, except refunds above $500. L3 escalations. Policy exceptions. Emergency authorisations |
| Executive | Everything a Department Head can. L4 escalations |
| Finance Reviewer | Refunds from $51 up to $1,000. Nothing else |
| VP Finance | Refunds of any amount. Nothing else |
| System Administrator | Nothing. Manages accounts, settings and policy documents only |

## Approval by Action

| Action | Minimum approver |
|---|---|
| Standard resolution (no money) | Tier 1 Agent |
| Re-route within the same team | Team Lead |
| Cross-team transfer of ownership | Team Manager of both teams |
| Escalation to L1 | Team Lead |
| Escalation to L2 | Team Manager |
| Escalation to L3 | Department Head |
| Escalation to L4 | Executive |
| Refund or credit up to $50 | Tier 1 Agent |
| Refund or credit $51 to $200 | Team Lead |
| Refund or credit $201 to $500 | Team Manager |
| Refund or credit $501 to $1,000 | Finance Reviewer |
| Refund or credit over $1,000 | VP Finance |
| Reverse an escalation | Team Manager or above |
| Close without resolution (customer unreachable) | Team Lead |
| Exception to a policy rule | Department Head, plus the normal approver for the amount |
| Restrict or end contact with an abusive customer | Team Manager |

An escalation to level N is approved by the role that owns level N, or by a higher support role.

## Rules

1. **Final action decides.** Authority is checked against the action that will actually be carried out. If an approver changes the amount, level or team, the changed action must be within that approver's authority.
2. **Refund amounts add up.** The amount is the total refunded to one customer for one case. Splitting a refund into smaller parts to stay under a limit is prohibited.
3. **Refunds above $500 belong to Finance.** Support leadership cannot approve them, whatever their level.
4. **No self-approval.** Nobody approves an action they requested or own. If the only eligible approver is the case owner, the request goes to the next level up.
5. **AI is never an approver.** FlowMind recommends. A named person approves.
6. **System Administrators have no approval authority** and have no access to customer personal data by default. Any administrator access to a case is logged.
7. **Response times.** Approvers MUST respond within the level time in the Escalation Policy: L1 4 hours, L2 2 hours, L3 1 hour, L4 immediately. Finance Reviewer 1 business day. VP Finance 2 business days. A request not answered in time moves automatically to the next level up and the approver's manager is notified.
8. **Reasons are mandatory.** Rejecting needs a written reason. Changing an action needs a written note. Both are recorded.
9. **Delegation.** An absent approver may delegate in writing to someone at the same level, for at most 14 days. Authority is never delegated downward.
10. **Emergencies.** In a safety or security emergency the Department Head may authorise verbally. The authorisation MUST be recorded within 1 business day.
11. **Records.** Every approval records who approved, the exact action (including amount, level and team), when, and the reason. Records are kept for 7 years.

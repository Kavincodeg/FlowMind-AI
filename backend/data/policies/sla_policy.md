# SLA Policy

## Document Control

| Field | Value |
|---|---|
| Version | 1.0 |
| Effective date | 2026-10-08 |
| Owner | Head of Support |
| Review cycle | Every 6 months |

## Purpose
This document defines the Service Level Agreement (SLA) response and resolution timeframes for customer support tickets based on priority and issue category.

## Priority Definitions

| Priority | Definition |
|---|---|
| High | Business-critical issue affecting core product functionality or involving financial loss > $100 |
| Medium | Significant inconvenience with a workaround available, or delayed service |
| Low | Minor issue with no immediate business impact |

## SLA Timeframes

| Priority | First Response | Resolution Target |
|---|---|---|
| High | 1 hour | 1 business day |
| Medium | 4 hours | 2 business days |
| Low | 8 hours | 5 business days |

All timeframes are measured from case creation, subject to the Business Hours and Clocks section below.

## Category-Specific SLA Notes

- **Billing disputes**: Must have first response within 2 hours regardless of priority. Resolution within 2 business days for all priorities (financial regulatory requirement).
- **Account access**: First response within 30 minutes for high priority (security risk). System access issues are auto-escalated after 4 hours.
- **Delivery**: Resolution clock pauses if issue is with third-party logistics provider — must be documented.
- **Product defect**: High-priority defects require engineering team involvement; SLA extends to 3 business days.
- **Service quality**: Resolution target includes documented corrective action or apology.

## Business Hours and Clocks

- Business hours are Monday to Friday, 09:00 to 18:00 in the company time zone, excluding public holidays. A "business day" is one business-hours day.
- The High priority first-response clock runs 24 hours a day, every day. All other clocks run only during business hours.
- A clock pauses while a case is Waiting on Customer, or while a documented third-party delay applies. It restarts when the customer replies or the delay ends.
- A case in Waiting for Approval keeps its clock running.

## SLA Breach Handling

- A ticket is marked `sla_breach=true` automatically when the resolution deadline passes without a `status=resolved` update.
- SLA-breached tickets trigger mandatory escalation (see Escalation Policy).
- All SLA breaches must be recorded in the audit log with root cause analysis within 5 business days.

## Measurement and Reporting

SLA performance is reported weekly by team managers. KPIs:
- First Response Rate (target: 95% within SLA)
- Resolution Rate (target: 90% within SLA)
- SLA Breach Rate (target: < 5% per month)

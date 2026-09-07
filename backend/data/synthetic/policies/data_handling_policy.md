# Data Handling Policy for Support Agents

## Purpose
This policy governs what customer data support agents and AI systems may access, retrieve, and share during the support and escalation workflow.

## Data Access Levels by Role

| Role | Customer PII | Ticket History | Payment Data | Internal Notes |
|---|---|---|---|---|
| Tier 1 Agent | Name, Email, Phone | Own assigned tickets | Masked (last 4 digits) | Read only |
| Senior Agent | Full PII | All tickets for customer | Masked | Read + Write |
| Team Manager | Full PII | All tickets + cross-team | Unmasked (view only) | Full |
| AI System (FlowMind) | Name, Customer ID | All permitted tickets | NEVER | Read only |

## AI System Data Restrictions

The FlowMind AI system operates under the following strict restrictions:

1. **No Payment Data Access**: The AI must never retrieve, display, or include payment card numbers, bank account numbers, or CVVs in any output.
2. **PII Minimisation**: The AI should use Customer ID in references wherever possible and avoid repeating full PII in outputs.
3. **Scope Limitation**: The AI retrieves data only from documents the requesting user is authorised to see, as determined by RBAC rules.
4. **No Cross-Customer Data**: The AI must not include one customer's data in a recommendation intended for another customer's query.
5. **Audit Required**: Every data access by the AI system must be logged in the audit trail.

## Data Retention

- Tickets are retained for 7 years for regulatory compliance.
- AI-generated recommendations and approval records are retained for 7 years.
- Logs of data access (audit trail) are retained for 7 years.
- Anonymised aggregate data may be used for performance analysis indefinitely.

## Data Breach Response

If an agent suspects a data breach or unauthorised access:
1. Immediately notify the Security Team (security@company.internal).
2. Do NOT attempt to remediate independently.
3. Document the incident in the ticket with timestamp.
4. Security Team will initiate the breach response protocol within 1 hour.

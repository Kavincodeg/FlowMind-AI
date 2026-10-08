/**
 * Shared policy display title mapping (Task 4)
 * Guarantees policy source names display as proper titles
 * (e.g., "SLA Policy", NOT naive title-case "Sla Policy").
 */

export const POLICY_TITLE_MAP: Record<string, string> = {
  'data_handling_policy.md': 'Data Handling Policy',
  'data_handling_policy': 'Data Handling Policy',
  'escalation_policy.md': 'Escalation Policy',
  'escalation_policy': 'Escalation Policy',
  'refund_policy.md': 'Refund Policy',
  'refund_policy': 'Refund Policy',
  'sla_policy.md': 'SLA Policy',
  'sla_policy': 'SLA Policy',
  'team_routing.md': 'Team Routing Guide',
  'team_routing': 'Team Routing Guide',
};

export function getPolicyDisplayTitle(sourceOrFilename: string | null | undefined): string {
  if (!sourceOrFilename) return 'Company Policy';
  const clean = sourceOrFilename.trim();
  const lower = clean.toLowerCase();

  if (POLICY_TITLE_MAP[lower]) {
    return POLICY_TITLE_MAP[lower];
  }

  const withMd = lower.endsWith('.md') ? lower : `${lower}.md`;
  if (POLICY_TITLE_MAP[withMd]) {
    return POLICY_TITLE_MAP[withMd];
  }

  const withoutMd = lower.replace(/\.md$/i, '');
  if (POLICY_TITLE_MAP[withoutMd]) {
    return POLICY_TITLE_MAP[withoutMd];
  }

  if (lower.startsWith('ticket-') || lower.startsWith('ticket_') || lower.startsWith('tkt-')) {
    return `Ticket ${clean.replace(/^[a-z]+[-_]/i, '').toUpperCase()}`;
  }

  return clean
    .replace(/\.md$/i, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

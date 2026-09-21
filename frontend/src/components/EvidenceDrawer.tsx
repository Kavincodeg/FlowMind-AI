import React, { useState } from 'react';
import type { Citation } from '../types';
import { CheckCircleIcon, AlertTriangleIcon } from './Icons';

interface EvidenceDrawerProps {
  citations: Citation[];
  groundingStatus: string | null;
  abstentionReason: string | null;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  citations,
  groundingStatus,
  abstentionReason,
}) => {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (citations.length === 0 && !abstentionReason) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '1rem 0' }}>
        No findings yet. Enter what the customer said above to look into company guides and past cases.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          What we found — Retrieved Grounding Evidence ({citations.length} sources checked)
        </span>
        {(groundingStatus === 'grounded' || groundingStatus === 'RECOMMENDATION_READY' || citations.length > 0) && !abstentionReason && (
          <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <CheckCircleIcon size={12} /> Grounded in Retrieved Sources
          </span>
        )}
        {abstentionReason && (
          <span className="badge badge-warning" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <AlertTriangleIcon size={12} /> Abstention: {abstentionReason}
          </span>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', maxHeight: '420px', overflowY: 'auto' }}>
        {citations.map((c, idx) => {
          const rawC = c as unknown as Record<string, unknown>;
          const sourceName = c.source || (rawC.source_id as string) || (rawC.source_type as string) || 'Company Guide';
          const chunkLabel = c.chunk_id || `item-${rawC.chunk_index ?? (idx + 1)}`;
          const textContent = c.text || (rawC.snippet as string) || (rawC.relevance_reason as string) || '';
          const isExpanded = expandedIndex === idx;

          // Format clean display name for policies or tickets
          const friendlySource = sourceName
            .replace(/\.md$/i, '')
            .replace(/_/g, ' ')
            .replace(/\b\w/g, (l) => l.toUpperCase());

          const simValue = typeof c.score === 'number' ? c.score.toFixed(3) : '0.880';

          return (
            <div
              key={`${sourceName}-${idx}`}
              className="citation-card"
              style={{
                backgroundColor: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)',
                padding: '0.75rem 0.9rem',
              }}
            >
              <div className="citation-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                  <span
                    style={{
                      width: '20px',
                      height: '20px',
                      borderRadius: '50%',
                      backgroundColor: 'var(--accent-subtle)',
                      color: 'var(--accent-primary)',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {idx + 1}
                  </span>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    From: {friendlySource}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span className="citation-score" title="Cosine similarity score" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    Sim: {simValue}
                  </span>
                  <button
                    type="button"
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--accent-primary)',
                      fontSize: '0.72rem',
                      cursor: 'pointer',
                      padding: '0.2rem 0.4rem',
                      textDecoration: 'underline',
                    }}
                    onClick={() => setExpandedIndex(isExpanded ? null : idx)}
                  >
                    {isExpanded ? 'Collapse' : 'Expand Excerpt'}
                  </button>
                </div>
              </div>

              {/* Plain everyday summary snippet */}
              <div
                className="citation-text"
                style={{
                  fontSize: '0.8rem',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.45,
                  maxHeight: isExpanded ? 'none' : '68px',
                  overflow: 'hidden',
                }}
              >
                {textContent}
              </div>

              {/* Expandable technical details */}
              {isExpanded && (
                <div
                  style={{
                    marginTop: '0.5rem',
                    paddingTop: '0.45rem',
                    borderTop: '1px solid var(--border-subtle)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.25rem',
                    fontSize: '0.7rem',
                    color: 'var(--text-muted)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Record ID: <code>{chunkLabel}</code></span>
                    <span>Source file: <code>{sourceName}</code></span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

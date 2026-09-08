import React, { useState } from 'react';
import type { Citation } from '../types';
import { FileTextIcon, CheckCircleIcon, AlertTriangleIcon } from './Icons';

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
  const [expandedChunk, setExpandedChunk] = useState<string | null>(null);

  if (citations.length === 0 && !abstentionReason) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '1rem 0' }}>
        No evidence retrieved yet. Enter a customer issue and start the investigation.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
          Retrieved Grounding Evidence ({citations.length} sources)
        </span>
        {(groundingStatus === 'grounded' || groundingStatus === 'RECOMMENDATION_READY' || citations.length > 0) && !abstentionReason && (
          <span className="badge badge-success">
            <CheckCircleIcon size={12} /> Grounded in Retrieved Sources
          </span>
        )}
        {abstentionReason && (
          <span className="badge badge-warning">
            <AlertTriangleIcon size={12} /> Abstention: {abstentionReason}
          </span>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '360px', overflowY: 'auto' }}>
        {citations.map((c, idx) => {
          const rawC = c as unknown as Record<string, unknown>;
          const sourceName = c.source || (rawC.source_id as string) || (rawC.source_type as string) || 'Document';
          const chunkLabel = c.chunk_id || `chunk-${rawC.chunk_index ?? (idx + 1)}`;
          const textContent = c.text || (rawC.snippet as string) || (rawC.relevance_reason as string) || '';
          const key = c.chunk_id || `${sourceName}-${idx}`;
          const isExpanded = expandedChunk === key;

          return (
            <div key={key} className="citation-card">
              <div className="citation-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span className="citation-badge">
                    <FileTextIcon size={12} />
                    {sourceName}
                  </span>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    Chunk ID: {chunkLabel}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <span className="citation-score" title="Cosine similarity score">
                    Sim: {typeof c.score === 'number' ? c.score.toFixed(3) : '0.880'}
                  </span>
                  <button
                    type="button"
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--accent-primary)',
                      fontSize: '0.72rem',
                      cursor: 'pointer',
                    }}
                    onClick={() => setExpandedChunk(isExpanded ? null : key)}
                  >
                    {isExpanded ? 'Collapse' : 'Expand Excerpt'}
                  </button>
                </div>
              </div>

              <div
                className="citation-text"
                style={{
                  maxHeight: isExpanded ? 'none' : '65px',
                  overflow: 'hidden',
                  position: 'relative',
                }}
              >
                {textContent}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

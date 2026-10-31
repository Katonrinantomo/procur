import { formatDateTime } from '../lib/format'
import { DECISION_LABEL, OUTCOME_LABEL, snapshotLine } from '../lib/decisions'
import type { DecisionRow } from '../types/api'

export default function DecisionHistory({ decisions }: { decisions: DecisionRow[] }) {
  if (decisions.length === 0) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <span style={{ fontSize: 12, color: '#6B6B66' }}>Decision history</span>
      <ol style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {[...decisions].reverse().map((d) => {
          const snap = snapshotLine(d)
          return (
            <li key={d.id} style={{ borderLeft: '2px solid #E0E0DB', paddingLeft: 12, display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ fontSize: 14, color: '#1A1A1A' }}>
                <span style={{ fontWeight: 500 }}>{DECISION_LABEL[d.decision] ?? d.decision}</span>
                {' · '}{d.username ?? 'unknown'}{d.role ? ` (${d.role})` : ''}
                {d.outcome_tag && (
                  <span style={{
                    marginLeft: 8,
                    fontSize: 12,
                    fontWeight: 500,
                    padding: '2px 6px',
                    borderRadius: 6,
                    color: '#3F3F3B',
                    background: '#F0F0EC',
                  }}>
                    {OUTCOME_LABEL[d.outcome_tag]}
                  </span>
                )}
              </span>
              <span style={{ fontSize: 12, color: '#6B6B66', fontFamily: "'Geist Mono', monospace", fontVariantNumeric: 'tabular-nums' }}>
                {formatDateTime(d.created_at)}
              </span>
              {d.reason && <p style={{ margin: 0, fontSize: 14, color: '#4A4A46' }}>{d.reason}</p>}
              {snap && <span style={{ fontSize: 12, color: '#6B6B66' }}>{snap}</span>}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

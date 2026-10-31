import { useState } from 'react'
import QueueTable from './QueueTable'
import Inspector from './Inspector'
import { SkeletonRows } from './SkeletonRow'
import { useReview } from '../hooks/useReview'
import { useRequestItem } from '../hooks/useRequestItem'

interface ReviewPageProps {
  role: string | null
}

/**
 * Owner's landing page: every row still waiting for a decision, across dates.
 * The backend sorts it (flagged first, then risk score descending).
 */
export default function ReviewPage({ role }: ReviewPageProps) {
  const { data, isLoading, isError, refetch } = useReview()
  const [pickedId, setPickedId] = useState<number | null>(null)
  const rows = data?.rows ?? []

  // The first row until the owner picks one. A decided row stays selected (it
  // leaves the list) so its new decision history is visible.
  const selectedId = pickedId ?? rows[0]?.id ?? null
  const { data: detail, isLoading: detailLoading } = useRequestItem(selectedId)

  const flaggedCount = rows.filter((r) => r.status === 'flagged').length

  return (
    <main style={{
      width: '100%',
      maxWidth: 1240,
      margin: '0 auto',
      boxSizing: 'border-box',
      padding: '28px 28px 40px',
      display: 'flex',
      flexDirection: 'column',
      gap: 28,
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#1A1A1A' }}>Review</h1>
        {data && (
          <p style={{ margin: 0, fontSize: 14, color: '#6B6B66' }}>
            <span style={{ fontFamily: "'Geist Mono', monospace", fontVariantNumeric: 'tabular-nums' }}>{rows.length}</span>
            {' '}{rows.length === 1 ? 'row' : 'rows'} waiting for a decision ·{' '}
            <span style={{ fontFamily: "'Geist Mono', monospace", fontVariantNumeric: 'tabular-nums' }}>{flaggedCount}</span>
            {' '}flagged
          </p>
        )}
      </div>

      {isError && (
        <div style={{
          padding: '12px 16px',
          border: '1px solid #FDEBDD',
          borderRadius: 8,
          color: '#9A3412',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}>
          <span>Failed to load the review list.</span>
          <button
            type="button"
            onClick={() => { void refetch() }}
            style={{
              height: 32,
              padding: '0 12px',
              border: '1px solid #9A3412',
              borderRadius: 6,
              background: 'transparent',
              color: '#9A3412',
              font: 'inherit',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
      )}

      {isLoading && (
        <div style={{ border: '1px solid #E6E6E2', borderRadius: 12, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 1180 }}>
            <tbody>
              <SkeletonRows count={4} />
            </tbody>
          </table>
        </div>
      )}

      {!isLoading && !isError && rows.length === 0 && (
        <div style={{ textAlign: 'center', padding: '80px 0', color: '#6B6B66', fontSize: 15 }}>
          Nothing waiting for a decision.
        </div>
      )}

      {rows.length > 0 && (
        <QueueTable rows={rows} selectedId={selectedId} onSelect={setPickedId} review />
      )}

      {selectedId !== null && (
        <Inspector detail={detail} isLoading={detailLoading} role={role} onDecided={setPickedId} />
      )}
    </main>
  )
}

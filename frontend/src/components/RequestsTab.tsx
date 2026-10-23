import { useEffect, useState } from 'react'
import { useRequestHistory } from '../hooks/useRequestHistory'
import { useRequestItem } from '../hooks/useRequestItem'
import QueueTable from './QueueTable'
import Inspector from './Inspector'
import type { QueueRow } from '../types/api'

const ALL_STATUSES = ['All', 'Flagged', 'New', 'Checked', 'Approved', 'Returned']

const MONO: React.CSSProperties = {
  fontFamily: "'Geist Mono', monospace",
  fontVariantNumeric: 'tabular-nums',
}

const INPUT_STYLE: React.CSSProperties = {
  border: '1px solid #E0E0DB',
  borderRadius: 8,
  height: 36,
  padding: '0 10px',
  font: 'inherit',
  fontSize: 14,
  background: '#fff',
  color: '#1A1A1A',
  boxSizing: 'border-box',
}

function defaultDateFrom(): string {
  const d = new Date()
  d.setDate(d.getDate() - 90)
  return d.toISOString().slice(0, 10)
}

function defaultDateTo(): string {
  // Yesterday: exclude today's rows
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

function statusToFilter(chip: string): string {
  if (chip === 'All') return 'all'
  return chip.toLowerCase()
}

export default function RequestsTab() {
  const [dateFrom, setDateFrom] = useState(defaultDateFrom)
  const [dateTo, setDateTo] = useState(defaultDateTo)
  const [activeStatus, setActiveStatus] = useState('All')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data, isLoading } = useRequestHistory({
    dateFrom,
    dateTo,
    status: statusToFilter(activeStatus),
    page,
  })

  const { data: detail, isLoading: detailLoading } = useRequestItem(selectedId)

  // Auto-select first row on load / data change
  useEffect(() => {
    if (!data || data.rows.length === 0) { setSelectedId(null); return }
    if (selectedId === null || !data.rows.find((r: QueueRow) => r.id === selectedId)) {
      setSelectedId(data.rows[0].id)
    }
  }, [data])  // eslint-disable-line react-hooks/exhaustive-deps

  const totalPages = data ? Math.ceil(data.total_count / data.page_size) : 1

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Filter row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); setPage(1) }}
          style={{ ...INPUT_STYLE, width: 148 }}
        />
        <span style={{ color: '#6B6B66', fontSize: 13 }}>to</span>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); setPage(1) }}
          style={{ ...INPUT_STYLE, width: 148 }}
        />
      </div>

      {/* Status chips */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {ALL_STATUSES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => { setActiveStatus(s); setPage(1) }}
            style={{
              padding: '7px 12px',
              borderRadius: 999,
              border: activeStatus === s ? 0 : '1px solid #E0E0DB',
              background: activeStatus === s ? '#1A1A1A' : 'transparent',
              color: activeStatus === s ? '#FFFFFF' : 'inherit',
              font: 'inherit',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Summary */}
      {data && (
        <div style={{ fontSize: 13, color: '#5E5E59' }}>
          <span style={MONO}>{data.total_count.toLocaleString('id-ID')} items</span>
        </div>
      )}

      {/* Table */}
      {isLoading && (
        <div style={{ padding: '32px', textAlign: 'center', color: '#9A9A95', border: '1px solid #E6E6E2', borderRadius: 12 }}>
          Loading…
        </div>
      )}

      {!isLoading && data && data.rows.length === 0 && (
        <div style={{
          padding: '48px 16px',
          textAlign: 'center',
          color: '#6B6B66',
          border: '1px solid #E6E6E2',
          borderRadius: 12,
          fontSize: 15,
        }}>
          No request items found for this range.
        </div>
      )}

      {!isLoading && data && data.rows.length > 0 && (
        <QueueTable
          rows={data.rows}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
      )}

      {/* Pagination */}
      {data && data.total_count > data.page_size && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 13, color: '#4A4A46' }}>
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            style={{
              height: 32,
              padding: '0 12px',
              border: '1px solid #E0E0DB',
              borderRadius: 6,
              background: 'transparent',
              font: 'inherit',
              fontSize: 13,
              cursor: page <= 1 ? 'default' : 'pointer',
              color: page <= 1 ? '#BDBDB8' : '#1A1A1A',
            }}
          >
            ← Previous
          </button>
          <span style={MONO}>
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            style={{
              height: 32,
              padding: '0 12px',
              border: '1px solid #E0E0DB',
              borderRadius: 6,
              background: 'transparent',
              font: 'inherit',
              fontSize: 13,
              cursor: page >= totalPages ? 'default' : 'pointer',
              color: page >= totalPages ? '#BDBDB8' : '#1A1A1A',
            }}
          >
            Next →
          </button>
        </div>
      )}

      {/* Inspector — renders below table */}
      {selectedId !== null && (
        <Inspector detail={detail} isLoading={detailLoading} />
      )}
    </div>
  )
}

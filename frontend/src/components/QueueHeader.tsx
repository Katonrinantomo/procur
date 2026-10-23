import FilterChips from './FilterChips'
import type { QueueRow, StatusCounts } from '../types/api'

interface QueueHeaderProps {
  rows: QueueRow[]
  counts: StatusCounts
  activeFilter: string
  onFilterChange: (value: string) => void
}

export default function QueueHeader({ rows, counts, activeFilter, onFilterChange }: QueueHeaderProps) {
  // Derive the display date from the first row's requested_at (Jakarta day) or today
  const dateStr = (() => {
    const d = rows[0]?.requested_at ? new Date(rows[0].requested_at) : new Date()
    return d.toLocaleDateString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      timeZone: 'Asia/Jakarta',
    })
  })()

  const total = counts.flagged + counts.new + counts.checked + counts.approved + counts.returned + counts.pending

  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      gap: 16,
      flexWrap: 'wrap',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>
          Requests · {dateStr}
        </h1>
        {rows.length > 0 && (
          <span style={{ fontSize: 13, color: '#6B6B66' }}>
            {total} requests · {counts.checked} checked · {counts.new} new item · {counts.flagged} flagged
          </span>
        )}
      </div>
      <FilterChips counts={counts} active={activeFilter} onChange={onFilterChange} />
    </div>
  )
}

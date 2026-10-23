import type { StatusCounts } from '../types/api'

interface FilterChipsProps {
  counts: StatusCounts
  active: string
  onChange: (value: string) => void
}

export default function FilterChips({ counts, active, onChange }: FilterChipsProps) {
  const total = counts.flagged + counts.new + counts.checked + counts.approved + counts.returned + counts.pending

  const chips = [
    { label: 'All', value: 'All', count: total },
    { label: 'Flagged', value: 'Flagged', count: counts.flagged },
    { label: 'New', value: 'New', count: counts.new },
    { label: 'Checked', value: 'Checked', count: counts.checked },
  ]

  return (
    <div style={{ display: 'flex', gap: 6, fontSize: 13, flexWrap: 'wrap' }}>
      {chips.map(({ label, value, count }) => (
        <button
          key={value}
          type="button"
          onClick={() => onChange(value)}
          style={{
            padding: '7px 12px',
            borderRadius: 999,
            border: active === value ? 0 : '1px solid #E0E0DB',
            background: active === value ? '#1A1A1A' : 'transparent',
            color: active === value ? '#FFFFFF' : 'inherit',
            font: 'inherit',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          {label} {count}
        </button>
      ))}
    </div>
  )
}

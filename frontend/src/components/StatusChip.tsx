type Status = 'flagged' | 'new' | 'checked' | 'approved' | 'returned' | 'pending'

const LABEL: Record<string, string> = {
  flagged: 'Flagged',
  new: 'New item',
  checked: 'Checked',
  approved: 'Approved',
  returned: 'Returned',
  pending: 'Pending',
}

const STYLES: Record<string, React.CSSProperties> = {
  flagged: { color: '#9A3412', background: '#FDEBDD' },
  new: { color: '#1E3A8A', background: '#E8EEFB' },
  checked: { color: '#3F3F3B', background: '#F0F0EC' },
  approved: { color: '#166534', background: '#E7F4EC' },
  returned: { color: '#4A4A46', background: '#FFFFFF', border: '1px solid #E0E0DB' },
  pending: { color: '#4A4A46', background: '#F0F0EC' },
}

interface StatusChipProps {
  status: Status | string
}

export default function StatusChip({ status }: StatusChipProps) {
  const style = STYLES[status] ?? STYLES.pending
  return (
    <span style={{
      display: 'inline-block',
      fontSize: 12,
      fontWeight: 500,
      padding: '4px 8px',
      borderRadius: 6,
      ...style,
    }}>
      {LABEL[status] ?? status}
    </span>
  )
}

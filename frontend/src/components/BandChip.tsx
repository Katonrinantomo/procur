/**
 * BandChip — price band or recommendation as a word on a tinted chip.
 * The value always comes from the backend (pricing.py), never the model.
 */

const STYLES: Record<string, { bg: string; text: string; label?: string }> = {
  'KOMPETITIF': { bg: '#E8EEFB', text: '#1E3A8A' },
  'WAJAR': { bg: '#E7F4EC', text: '#166534' },
  'PERHATIAN': { bg: '#FFF4EC', text: '#9A3412' },
  'TIDAK WAJAR': { bg: '#FDEBDD', text: '#9A3412' },
  'SETUJU': { bg: '#E7F4EC', text: '#166534' },
  'NEGOSIASI': { bg: '#FFF4EC', text: '#9A3412' },
  'TOLAK': { bg: '#FDEBDD', text: '#9A3412' },
  'UNKNOWN': { bg: '#F0F0EC', text: '#3F3F3B', label: 'data tidak cukup' },
}

export default function BandChip({ value, style }: { value: string | null | undefined; style?: React.CSSProperties }) {
  if (!value) return null
  const s = STYLES[value]
  if (!s) return null
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 6px',
      fontSize: 12,
      borderRadius: 6,
      background: s.bg,
      color: s.text,
      fontWeight: 500,
      whiteSpace: 'nowrap',
      ...style,
    }}>
      {s.label ?? value}
    </span>
  )
}

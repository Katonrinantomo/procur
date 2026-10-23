function SkeletonCell() {
  return (
    <td style={{ padding: '13px 16px' }}>
      <div style={{
        height: 14,
        borderRadius: 4,
        background: '#E8E8E4',
        animation: 'pulse 1.5s ease-in-out infinite',
      }} />
    </td>
  )
}

export function SkeletonRow() {
  return (
    <tr style={{ borderTop: '1px solid #EDEDEA' }}>
      {Array.from({ length: 9 }).map((_, i) => <SkeletonCell key={i} />)}
    </tr>
  )
}

interface SkeletonRowsProps {
  count?: number
}

export function SkeletonRows({ count = 4 }: SkeletonRowsProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => <SkeletonRow key={i} />)}
    </>
  )
}

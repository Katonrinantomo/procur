import StatusChip from './StatusChip'
import { formatRupiah, formatPct, formatDate } from '../lib/format'
import type { QueueRow } from '../types/api'

interface QueueTableProps {
  rows: QueueRow[]
  selectedId: number | null
  onSelect: (id: number) => void
  // Review page: adds Entered by, Requested and Risk columns
  review?: boolean
}

function checkedViaText(row: QueueRow): string {
  if (row.checked_via === 'history') {
    return row.history_count != null ? `History · ${row.history_count} buys` : 'History'
  }
  if (row.checked_via === 'web') {
    return row.web_quote_count != null ? `Web · ${row.web_quote_count} quotes` : 'Web'
  }
  return '—'
}

function rowStyle(row: QueueRow, isSelected: boolean): React.CSSProperties {
  if (row.status === 'flagged') {
    return {
      borderTop: '1px solid #EDEDEA',
      background: '#FFF8F2',
      boxShadow: 'inset 3px 0 0 #9A3412',
      cursor: 'pointer',
    }
  }
  if (isSelected) {
    return {
      borderTop: '1px solid #EDEDEA',
      background: '#F5F5F2',
      cursor: 'pointer',
    }
  }
  return {
    borderTop: '1px solid #EDEDEA',
    cursor: 'pointer',
  }
}

const NUM_CELL: React.CSSProperties = {
  padding: '13px 16px',
  textAlign: 'right',
  fontFamily: "'Geist Mono', monospace",
}

export default function QueueTable({ rows, selectedId, onSelect, review = false }: QueueTableProps) {
  return (
    <div style={{ border: '1px solid #E6E6E2', borderRadius: 12, overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: review ? 1180 : 980 }}>
        <thead>
          <tr style={{ background: '#F7F7F5', textAlign: 'left', fontSize: 12, color: '#5E5E59' }}>
            <th style={{ padding: '11px 16px', fontWeight: 500 }}>#</th>
            <th style={{ padding: '11px 16px', fontWeight: 500 }}>Item</th>
            {review && <th style={{ padding: '11px 16px', fontWeight: 500 }}>Entered by</th>}
            {review && <th style={{ padding: '11px 16px', fontWeight: 500 }}>Requested</th>}
            <th style={{ padding: '11px 16px', fontWeight: 500 }}>Dept.</th>
            <th style={{ padding: '11px 16px', fontWeight: 500, textAlign: 'right' }}>Qty</th>
            <th style={{ padding: '11px 16px', fontWeight: 500, textAlign: 'right' }}>Quoted / unit</th>
            <th style={{ padding: '11px 16px', fontWeight: 500, textAlign: 'right' }}>Reference / unit</th>
            <th style={{ padding: '11px 16px', fontWeight: 500, textAlign: 'right' }}>Diff.</th>
            <th style={{ padding: '11px 16px', fontWeight: 500 }}>Checked via</th>
            {review && <th style={{ padding: '11px 16px', fontWeight: 500, textAlign: 'right' }}>Risk</th>}
            <th style={{ padding: '11px 16px', fontWeight: 500 }}>Status</th>
          </tr>
        </thead>
        <tbody style={{ fontVariantNumeric: 'tabular-nums' }}>
          {rows.map((row) => {
            const isSelected = row.id === selectedId
            const lineNo = String(row.line_no).padStart(2, '0')

            const diffColor = row.status === 'flagged' && row.diff_pct != null && row.diff_pct > 0
              ? '#9A3412'
              : '#6B6B66'

            return (
              <tr
                key={row.id}
                style={rowStyle(row, isSelected)}
                tabIndex={0}
                onClick={() => onSelect(row.id)}
                onKeyDown={(e) => { if (e.key === 'Enter') onSelect(row.id) }}
              >
                <td style={{ padding: '13px 16px', color: '#6B6B66' }}>{lineNo}</td>
                <td style={{ padding: '13px 16px', fontWeight: row.status === 'flagged' ? 500 : undefined }}>
                  {row.raw_name}
                </td>
                {review && <td style={{ padding: '13px 16px', color: '#4A4A46' }}>{row.entered_by ?? row.requested_by ?? '—'}</td>}
                {review && <td style={{ padding: '13px 16px', color: '#4A4A46', whiteSpace: 'nowrap' }}>{formatDate(row.requested_at)}</td>}
                <td style={{ padding: '13px 16px', color: '#4A4A46' }}>{row.department ?? '—'}</td>
                <td style={NUM_CELL}>
                  {row.qty != null ? `${row.qty} ${row.unit ?? ''}`.trim() : '—'}
                </td>
                <td style={NUM_CELL}>
                  {row.quoted_unit_price_idr != null ? formatRupiah(row.quoted_unit_price_idr) : '—'}
                </td>
                <td style={NUM_CELL}>
                  {row.reference_unit_price_idr != null ? formatRupiah(row.reference_unit_price_idr) : '—'}
                </td>
                <td style={{ ...NUM_CELL, color: diffColor, fontWeight: row.status === 'flagged' && row.diff_pct != null && row.diff_pct > 0 ? 500 : undefined }}>
                  {row.diff_pct != null ? formatPct(row.diff_pct) : '—'}
                </td>
                <td style={{ padding: '13px 16px', color: '#4A4A46' }}>{checkedViaText(row)}</td>
                {review && (
                  <td style={{ ...NUM_CELL, color: row.risk_score >= 50 ? '#9A3412' : '#4A4A46', fontWeight: row.risk_score >= 50 ? 500 : undefined }}>
                    {row.risk_score}
                  </td>
                )}
                <td style={{ padding: '13px 16px' }}>
                  <StatusChip status={row.status} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

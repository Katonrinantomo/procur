import { formatRupiah, formatDate } from '../lib/format'
import type { PurchaseOut } from '../types/api'

interface HistoryTableProps {
  purchases: PurchaseOut[]
  referencePrice: number | null
}

export default function HistoryTable({ purchases, referencePrice }: HistoryTableProps) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 460 }}>
        <thead>
          <tr style={{ textAlign: 'left', fontSize: 12, color: '#5E5E59', borderBottom: '1px solid #EDEDEA' }}>
            <th style={{ padding: '8px 10px 10px 0', fontWeight: 500 }}>Date</th>
            <th style={{ padding: '8px 10px 10px', fontWeight: 500 }}>PO no.</th>
            <th style={{ padding: '8px 10px 10px', fontWeight: 500 }}>Supplier</th>
            <th style={{ padding: '8px 10px 10px', fontWeight: 500, textAlign: 'right' }}>Qty</th>
            <th style={{ padding: '8px 0 10px 10px', fontWeight: 500, textAlign: 'right' }}>Price / unit</th>
          </tr>
        </thead>
        <tbody style={{ fontVariantNumeric: 'tabular-nums' }}>
          {purchases.map((p, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #F2F2EF' }}>
              <td style={{ padding: '11px 10px 11px 0' }}>{formatDate(p.purchase_date)}</td>
              <td style={{ padding: '11px 10px', fontFamily: "'Geist Mono', monospace", color: '#4A4A46' }}>
                {p.po_number ?? '—'}
              </td>
              <td style={{ padding: '11px 10px' }}>{p.supplier_name}</td>
              <td style={{ padding: '11px 10px', textAlign: 'right', fontFamily: "'Geist Mono', monospace" }}>
                {p.qty}
              </td>
              <td style={{ padding: '11px 0 11px 10px', textAlign: 'right', fontFamily: "'Geist Mono', monospace" }}>
                {formatRupiah(p.unit_price_idr)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td
              colSpan={4}
              style={{ padding: '12px 10px 0 0', fontSize: 13, color: '#5E5E59' }}
            >
              3-buy average (reference)
            </td>
            <td style={{
              padding: '12px 0 0 10px',
              textAlign: 'right',
              fontFamily: "'Geist Mono', monospace",
              fontWeight: 500,
            }}>
              {referencePrice != null ? formatRupiah(referencePrice) : '—'}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

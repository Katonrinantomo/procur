import { formatRupiah, formatDate } from '../lib/format'
import type { ItemPurchaseHistory } from '../types/api'

interface ItemPurchasePanelProps {
  history: ItemPurchaseHistory
  onClose: () => void
}

export default function ItemPurchasePanel({ history, onClose }: ItemPurchasePanelProps) {
  return (
    <div style={{
      border: '1px solid #E6E6E2',
      borderRadius: 12,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '14px 18px',
        borderBottom: '1px solid #E6E6E2',
        background: '#F7F7F5',
      }}>
        <div>
          <div style={{ fontSize: 13, color: '#5E5E59', marginBottom: 2 }}>Purchase history</div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{history.item_name}</div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close panel"
          style={{
            width: 28,
            height: 28,
            border: '1px solid #E0E0DB',
            borderRadius: 6,
            background: 'transparent',
            cursor: 'pointer',
            fontSize: 14,
            color: '#4A4A46',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          ✕
        </button>
      </div>

      {/* Table */}
      <div style={{ padding: '16px 18px', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 540 }}>
          <thead>
            <tr style={{ textAlign: 'left', fontSize: 12, color: '#5E5E59', borderBottom: '1px solid #EDEDEA' }}>
              <th style={{ padding: '8px 10px 10px 0', fontWeight: 500 }}>Date</th>
              <th style={{ padding: '8px 10px 10px', fontWeight: 500 }}>PO no.</th>
              <th style={{ padding: '8px 10px 10px', fontWeight: 500 }}>Supplier</th>
              <th style={{ padding: '8px 10px 10px', fontWeight: 500, textAlign: 'right' }}>Qty</th>
              <th style={{ padding: '8px 10px 10px', fontWeight: 500, textAlign: 'right' }}>Price / unit</th>
              <th style={{ padding: '8px 0 10px 10px', fontWeight: 500, textAlign: 'right' }}>Total</th>
            </tr>
          </thead>
          <tbody style={{ fontVariantNumeric: 'tabular-nums' }}>
            {history.last_purchases.map((p) => (
              <tr key={p.id} style={{ borderBottom: '1px solid #F2F2EF' }}>
                <td style={{ padding: '11px 10px 11px 0' }}>{formatDate(p.purchase_date)}</td>
                <td style={{ padding: '11px 10px', fontFamily: "'Geist Mono', monospace", color: '#4A4A46' }}>
                  {p.po_number ?? '—'}
                </td>
                <td style={{ padding: '11px 10px' }}>{p.supplier_name}</td>
                <td style={{ padding: '11px 10px', textAlign: 'right', fontFamily: "'Geist Mono', monospace" }}>
                  {p.qty} {p.unit}
                </td>
                <td style={{ padding: '11px 10px', textAlign: 'right', fontFamily: "'Geist Mono', monospace" }}>
                  {formatRupiah(p.unit_price_idr)}
                </td>
                <td style={{ padding: '11px 0 11px 10px', textAlign: 'right', fontFamily: "'Geist Mono', monospace" }}>
                  {formatRupiah(p.total_idr)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td
                colSpan={5}
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
                {history.reference_price_idr != null ? formatRupiah(history.reference_price_idr) : '—'}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}

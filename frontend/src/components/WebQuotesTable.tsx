import { formatRupiah } from '../lib/format'
import type { WebQuoteOut } from '../types/api'

interface WebQuotesTableProps {
  quotes: WebQuoteOut[]
  referencePrice: number | null
}

function _captureDate(quotes: WebQuoteOut[]): string | null {
  if (!quotes.length) return null
  // Use the newest fetched_at among the quotes.
  const newest = quotes.reduce((a, b) =>
    new Date(a.fetched_at) > new Date(b.fetched_at) ? a : b
  )
  return new Date(newest.fetched_at).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'Asia/Jakarta',
  })
}

export default function WebQuotesTable({ quotes, referencePrice }: WebQuotesTableProps) {
  const captureDate = _captureDate(quotes)

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 460 }}>
        <thead>
          <tr style={{ textAlign: 'left', fontSize: 12, color: '#5E5E59', borderBottom: '1px solid #EDEDEA' }}>
            <th style={{ padding: '8px 10px 10px 0', fontWeight: 500 }}>Seller</th>
            <th style={{ padding: '8px 10px 10px', fontWeight: 500 }}>Offer</th>
            <th style={{ padding: '8px 0 10px 10px', fontWeight: 500, textAlign: 'right' }}>Price / unit</th>
          </tr>
        </thead>
        <tbody style={{ fontVariantNumeric: 'tabular-nums' }}>
          {quotes.map((q, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #F2F2EF' }}>
              <td style={{ padding: '11px 10px 11px 0' }}>{q.seller ?? '—'}</td>
              <td style={{ padding: '11px 10px' }}>
                {q.url ? (
                  <a href={q.url} target="_blank" rel="noopener noreferrer" style={{ color: '#1A1A1A' }}>
                    {q.title ?? q.url}
                  </a>
                ) : (
                  q.title ?? '—'
                )}
              </td>
              <td style={{ padding: '11px 0 11px 10px', textAlign: 'right', fontFamily: "'Geist Mono', monospace" }}>
                {formatRupiah(q.price_idr)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td
              colSpan={2}
              style={{ padding: '12px 10px 0 0', fontSize: 13, color: '#5E5E59' }}
            >
              Median of {quotes.length} quotes (reference)
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
          {captureDate && (
            <tr>
              <td
                colSpan={3}
                style={{ padding: '6px 0 0', fontSize: 12, color: '#8A8A85' }}
              >
                All prices in Rp. Quotes captured {captureDate}.
              </td>
            </tr>
          )}
        </tfoot>
      </table>
    </div>
  )
}

import { formatRupiah, formatDate } from '../lib/format'
import { useItemSuppliers } from '../hooks/useItemSuppliers'
import type { WebQuoteOut } from '../types/api'

/** Accept only http/https URLs; anything else renders as plain text. */
function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null
  try {
    const p = new URL(url)
    if (p.protocol !== 'http:' && p.protocol !== 'https:') return null
    return url
  } catch {
    return null
  }
}

interface SupplierPanelProps {
  /** catalog item_id — null for new items (web quotes path) */
  itemId: number | null
  quotingSupplierName: string | null
  /** web quotes to show when itemId is null (new item) */
  webQuotes: WebQuoteOut[] | null
  onClose: () => void
}

const OVERLAY: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  zIndex: 40,
  display: 'flex',
  justifyContent: 'flex-end',
}

const BACKDROP: React.CSSProperties = {
  position: 'absolute',
  inset: 0,
  background: 'rgba(0,0,0,0.18)',
}

const PANEL: React.CSSProperties = {
  position: 'relative',
  zIndex: 1,
  width: '100%',
  maxWidth: 460,
  height: '100%',
  background: '#FFFFFF',
  borderLeft: '1px solid #E6E6E2',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
}

const TH: React.CSSProperties = {
  padding: '8px 10px 10px',
  fontWeight: 500,
  textAlign: 'left',
  fontSize: 12,
  color: '#5E5E59',
  whiteSpace: 'nowrap',
}

const TH_RIGHT: React.CSSProperties = { ...TH, textAlign: 'right' }

const TD: React.CSSProperties = {
  padding: '11px 10px',
  fontSize: 14,
  verticalAlign: 'middle',
}

const TD_MONO: React.CSSProperties = {
  ...TD,
  fontFamily: "'Geist Mono', monospace",
  fontVariantNumeric: 'tabular-nums',
}

const TD_RIGHT: React.CSSProperties = { ...TD_MONO, textAlign: 'right' }

export default function SupplierPanel({ itemId, quotingSupplierName, webQuotes, onClose }: SupplierPanelProps) {
  const isNewItem = itemId === null
  const { data, isLoading, isError } = useItemSuppliers(isNewItem ? null : itemId)

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') onClose()
  }

  return (
    <div style={OVERLAY} role="dialog" aria-modal aria-label="Compare suppliers" onKeyDown={handleKeyDown}>
      {/* backdrop */}
      <div style={BACKDROP} onClick={onClose} aria-hidden />

      <div style={PANEL}>
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '20px 24px 16px',
          borderBottom: '1px solid #EDEDEA',
          flexShrink: 0,
        }}>
          <span style={{ fontWeight: 600, fontSize: 15 }}>Compare suppliers</span>
          <button
            type="button"
            onClick={onClose}
            style={{
              width: 32,
              height: 32,
              border: '1px solid #E0E0DB',
              borderRadius: 8,
              background: '#FFFFFF',
              cursor: 'pointer',
              fontSize: 16,
              lineHeight: 1,
              color: '#4A4A46',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px 28px' }}>
          {isNewItem ? (
            /* New item — show web quotes */
            webQuotes && webQuotes.length > 0 ? (
              <>
                <p style={{ margin: '0 0 14px', fontSize: 13, color: '#6B6B66' }}>
                  No purchase history — showing web quotes.
                </p>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #EDEDEA' }}>
                        <th style={TH}>Source</th>
                        <th style={TH_RIGHT}>Price / unit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {webQuotes.map((wq, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid #F2F2EF' }}>
                          <td style={TD}>
                            {safeUrl(wq.url) ? (
                              <a href={safeUrl(wq.url)!} target="_blank" rel="noopener noreferrer" style={{ color: '#1A1A1A' }}>
                                {wq.seller ?? wq.title ?? wq.url}
                              </a>
                            ) : (
                              <span style={{ color: '#4A4A46' }}>{wq.seller ?? wq.title ?? '—'}</span>
                            )}
                          </td>
                          <td style={TD_RIGHT}>{formatRupiah(wq.price_idr)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p style={{ fontSize: 14, color: '#6B6B66' }}>No web quotes available.</p>
            )
          ) : isLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingTop: 4 }}>
              {[100, 80, 90].map((w, i) => (
                <div key={i} style={{ height: 14, width: `${w}%`, borderRadius: 4, background: '#E8E8E4', animation: 'pulse 1.5s ease-in-out infinite' }} />
              ))}
            </div>
          ) : isError || !data ? (
            <p style={{ fontSize: 14, color: '#9A3412' }}>Failed to load supplier data.</p>
          ) : data.suppliers.length === 0 ? (
            <p style={{ fontSize: 14, color: '#6B6B66' }}>No supplier history for this item.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #EDEDEA' }}>
                    <th style={TH}>Supplier</th>
                    <th style={TH_RIGHT}>Last price / unit</th>
                    <th style={TH_RIGHT}>Last bought</th>
                    <th style={TH_RIGHT}>Buys</th>
                  </tr>
                </thead>
                <tbody>
                  {data.suppliers.map((s) => {
                    const isQuoting = quotingSupplierName != null &&
                      s.supplier_name.toLowerCase() === quotingSupplierName.toLowerCase()
                    return (
                      <tr key={s.supplier_id} style={{ borderBottom: '1px solid #F2F2EF' }}>
                        <td style={TD}>
                          <span>{s.supplier_name}</span>
                          {isQuoting && (
                            <span style={{
                              marginLeft: 8,
                              fontSize: 11,
                              fontWeight: 500,
                              color: '#1E3A8A',
                              background: '#E8EEFB',
                              padding: '2px 6px',
                              borderRadius: 4,
                            }}>
                              quoting
                            </span>
                          )}
                        </td>
                        <td style={TD_RIGHT}>{formatRupiah(s.last_unit_price_idr)}</td>
                        <td style={{ ...TD_RIGHT, color: '#4A4A46' }}>{formatDate(s.last_purchase_date)}</td>
                        <td style={TD_RIGHT}>{s.buy_count}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

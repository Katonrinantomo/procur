import { useState } from 'react'
import { usePurchases } from '../hooks/usePurchases'
import { useSuppliers } from '../hooks/useSuppliers'
import { useItemPurchaseHistory } from '../hooks/useItemPurchaseHistory'
import ItemPurchasePanel from './ItemPurchasePanel'
import { formatRupiahWithPrefix, formatDate } from '../lib/format'

const MONO: React.CSSProperties = {
  fontFamily: "'Geist Mono', monospace",
  fontVariantNumeric: 'tabular-nums',
}

function defaultDateFrom(): string {
  const d = new Date()
  d.setDate(d.getDate() - 90)
  return d.toISOString().slice(0, 10)
}

function defaultDateTo(): string {
  return new Date().toISOString().slice(0, 10)
}

const INPUT_STYLE: React.CSSProperties = {
  border: '1px solid #E0E0DB',
  borderRadius: 8,
  height: 36,
  padding: '0 10px',
  font: 'inherit',
  fontSize: 14,
  background: '#fff',
  color: '#1A1A1A',
  boxSizing: 'border-box',
}

export default function PurchasesTab() {
  const [search, setSearch] = useState('')
  const [supplierId, setSupplierId] = useState('')
  const [dateFrom, setDateFrom] = useState(defaultDateFrom)
  const [dateTo, setDateTo] = useState(defaultDateTo)
  const [page, setPage] = useState(1)
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null)

  // Debounce search input slightly by using a separate committed state
  const [committedSearch, setCommittedSearch] = useState('')

  const { data, isLoading } = usePurchases({
    search: committedSearch,
    supplierId,
    dateFrom,
    dateTo,
    page,
  })

  const { data: suppliers } = useSuppliers()
  const { data: itemHistory, isLoading: historyLoading } = useItemPurchaseHistory(selectedItemId)

  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      setCommittedSearch(search)
      setPage(1)
    }
  }

  function handleFilterChange() {
    setCommittedSearch(search)
    setPage(1)
  }

  const totalPages = data ? Math.ceil(data.total_count / data.page_size) : 1

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Filter row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Search item, supplier, PO…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={handleSearchKeyDown}
          style={{ ...INPUT_STYLE, width: 220 }}
        />
        <select
          value={supplierId}
          onChange={(e) => { setSupplierId(e.target.value); setPage(1) }}
          style={{ ...INPUT_STYLE, width: 200 }}
        >
          <option value="">All suppliers</option>
          {suppliers?.map((s) => (
            <option key={s.id} value={String(s.id)}>{s.name}</option>
          ))}
        </select>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); setPage(1) }}
          style={{ ...INPUT_STYLE, width: 148 }}
        />
        <span style={{ color: '#6B6B66', fontSize: 13 }}>to</span>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); setPage(1) }}
          style={{ ...INPUT_STYLE, width: 148 }}
        />
        <button
          type="button"
          onClick={handleFilterChange}
          style={{
            height: 36,
            padding: '0 14px',
            border: '1px solid #E0E0DB',
            borderRadius: 8,
            background: 'transparent',
            color: '#1A1A1A',
            font: 'inherit',
            fontSize: 14,
            cursor: 'pointer',
          }}
        >
          Search
        </button>
      </div>

      {/* Summary line */}
      {data && (
        <div style={{ fontSize: 13, color: '#5E5E59', display: 'flex', gap: 16 }}>
          <span style={MONO}>{data.total_count.toLocaleString('id-ID')} purchases</span>
          <span>·</span>
          <span style={MONO}>{formatRupiahWithPrefix(data.total_amount_idr)} total</span>
        </div>
      )}

      {/* Table */}
      <div style={{ border: '1px solid #E6E6E2', borderRadius: 12, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 860 }}>
          <thead>
            <tr style={{ background: '#F7F7F5', textAlign: 'left', fontSize: 12, color: '#5E5E59' }}>
              <th style={{ padding: '11px 16px', fontWeight: 500 }}>Date</th>
              <th style={{ padding: '11px 16px', fontWeight: 500 }}>PO no.</th>
              <th style={{ padding: '11px 16px', fontWeight: 500 }}>Item</th>
              <th style={{ padding: '11px 16px', fontWeight: 500 }}>Supplier</th>
              <th style={{ padding: '11px 16px', fontWeight: 500, textAlign: 'right' }}>Qty</th>
              <th style={{ padding: '11px 16px', fontWeight: 500, textAlign: 'right' }}>Price / unit</th>
              <th style={{ padding: '11px 16px', fontWeight: 500, textAlign: 'right' }}>Total</th>
            </tr>
          </thead>
          <tbody style={{ fontVariantNumeric: 'tabular-nums' }}>
            {isLoading && (
              <tr>
                <td colSpan={7} style={{ padding: '32px 16px', textAlign: 'center', color: '#9A9A95' }}>
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && data?.rows.length === 0 && (
              <tr>
                <td colSpan={7} style={{ padding: '32px 16px', textAlign: 'center', color: '#9A9A95' }}>
                  No purchases found.
                </td>
              </tr>
            )}
            {!isLoading && data?.rows.map((row) => (
              <tr
                key={row.id}
                style={{ borderTop: '1px solid #EDEDEA', cursor: 'pointer', background: selectedItemId === row.item_id ? '#F5F5F2' : undefined }}
                onClick={() => setSelectedItemId(row.item_id === selectedItemId ? null : row.item_id)}
              >
                <td style={{ padding: '12px 16px', color: '#4A4A46' }}>{formatDate(row.purchase_date)}</td>
                <td style={{ padding: '12px 16px', ...MONO, color: '#4A4A46' }}>{row.po_number ?? '—'}</td>
                <td style={{ padding: '12px 16px', fontWeight: 500 }}>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); setSelectedItemId(row.item_id === selectedItemId ? null : row.item_id) }}
                    style={{
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      font: 'inherit',
                      fontSize: 14,
                      color: '#1A1A1A',
                      cursor: 'pointer',
                      textDecoration: 'underline',
                      textDecorationColor: '#BDBDB8',
                    }}
                  >
                    {row.item_name}
                  </button>
                </td>
                <td style={{ padding: '12px 16px', color: '#4A4A46' }}>{row.supplier_name}</td>
                <td style={{ padding: '12px 16px', textAlign: 'right', ...MONO }}>{row.qty} {row.unit}</td>
                <td style={{ padding: '12px 16px', textAlign: 'right', ...MONO }}>{formatRupiahWithPrefix(row.unit_price_idr)}</td>
                <td style={{ padding: '12px 16px', textAlign: 'right', ...MONO }}>{formatRupiahWithPrefix(row.total_idr)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.total_count > data.page_size && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 13, color: '#4A4A46' }}>
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            style={{
              height: 32,
              padding: '0 12px',
              border: '1px solid #E0E0DB',
              borderRadius: 6,
              background: 'transparent',
              font: 'inherit',
              fontSize: 13,
              cursor: page <= 1 ? 'default' : 'pointer',
              color: page <= 1 ? '#BDBDB8' : '#1A1A1A',
            }}
          >
            ← Previous
          </button>
          <span style={MONO}>
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            style={{
              height: 32,
              padding: '0 12px',
              border: '1px solid #E0E0DB',
              borderRadius: 6,
              background: 'transparent',
              font: 'inherit',
              fontSize: 13,
              cursor: page >= totalPages ? 'default' : 'pointer',
              color: page >= totalPages ? '#BDBDB8' : '#1A1A1A',
            }}
          >
            Next →
          </button>
        </div>
      )}

      {/* Item side panel */}
      {selectedItemId !== null && (
        <div>
          {historyLoading && (
            <div style={{ padding: '24px', border: '1px solid #E6E6E2', borderRadius: 12, color: '#9A9A95', textAlign: 'center' }}>
              Loading purchase history…
            </div>
          )}
          {itemHistory && (
            <ItemPurchasePanel
              history={itemHistory}
              onClose={() => setSelectedItemId(null)}
            />
          )}
        </div>
      )}
    </div>
  )
}

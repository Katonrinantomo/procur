import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import HistoryTable from './HistoryTable'
import WebQuotesTable from './WebQuotesTable'
import StatusChip from './StatusChip'
import SupplierPanel from './SupplierPanel'
import ReturnDialog from './ReturnDialog'
import { formatRupiah, formatRupiahWithPrefix, formatPct } from '../lib/format'
import { useApprove, useReturn } from '../hooks/useItemActions'
import { fetchWithAuth } from '../lib/api'
import type { RequestItemDetail } from '../types/api'

interface InspectorProps {
  detail: RequestItemDetail | undefined
  isLoading: boolean
  role?: string | null
}

function InspectorSkeleton() {
  return (
    <section
      aria-label="Selected item"
      style={{ border: '1px solid #E6E6E2', borderRadius: 12, display: 'flex', flexWrap: 'wrap' }}
    >
      <div style={{ flex: '1 1 340px', boxSizing: 'border-box', padding: 24, borderRight: '1px solid #EDEDEA', display: 'flex', flexDirection: 'column', gap: 18 }}>
        {[80, 140, 100, 100].map((w, i) => (
          <div key={i} style={{ height: i === 1 ? 24 : 14, width: `${w}%`, maxWidth: '100%', borderRadius: 4, background: '#E8E8E4', animation: 'pulse 1.5s ease-in-out infinite' }} />
        ))}
      </div>
      <div style={{ flex: '999 1 460px', minWidth: 0, boxSizing: 'border-box', padding: 24 }}>
        <div style={{ height: 14, width: '40%', borderRadius: 4, background: '#E8E8E4', animation: 'pulse 1.5s ease-in-out infinite' }} />
      </div>
    </section>
  )
}

export default function Inspector({ detail, isLoading, role }: InspectorProps) {
  const [supplierPanelOpen, setSupplierPanelOpen] = useState(false)
  const [returnDialogOpen, setReturnDialogOpen] = useState(false)
  const [rechecking, setRechecking] = useState(false)

  const qc = useQueryClient()
  const approveMutation = useApprove(detail?.id ?? 0)
  const returnMutation = useReturn(detail?.id ?? 0)

  if (isLoading || !detail) return <InspectorSkeleton />

  const lineNo = String(detail.line_no).padStart(2, '0')

  const requestedTime = new Date(detail.requested_at).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Jakarta',
  })
  const requesterLine = `Row ${lineNo} · Requested by ${detail.department ?? detail.requested_by ?? 'unknown'}, ${requestedTime}`

  const hasHistory = detail.checked_via === 'history' && detail.last_purchases && detail.last_purchases.length > 0
  const hasWebQuotes = detail.web_quotes && detail.web_quotes.length > 0
  const rightTitle = hasHistory ? 'Purchase history' : hasWebQuotes ? 'Web quotes' : null

  const isNewItem = detail.catalog_item_id === null
  const canAct = detail.status !== 'approved' && detail.status !== 'returned'
  const canRecheck = detail.status === 'approved' || detail.status === 'returned'

  function handleApprove() {
    if (!canAct) return
    approveMutation.mutate()
  }

  function handleReturnConfirm(note: string) {
    returnMutation.mutate(note, {
      onSuccess: () => setReturnDialogOpen(false),
    })
  }

  return (
    <>
      <section aria-label="Selected item" style={{ border: '1px solid #E6E6E2', borderRadius: 12, display: 'flex', flexWrap: 'wrap' }}>

        {/* Left half */}
        <div style={{
          flex: '1 1 340px',
          boxSizing: 'border-box',
          padding: 24,
          borderRight: '1px solid #EDEDEA',
          display: 'flex',
          flexDirection: 'column',
          gap: 18,
        }}>
          {/* Header */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: 12, color: '#6B6B66' }}>{requesterLine}</span>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{detail.raw_name}</h2>
          </div>

          {/* Flag box */}
          {detail.flags.length > 0 && (
            <div style={{ border: '1px solid #F2C7A5', background: '#FFF4EC', borderRadius: 10, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, fontWeight: 600, color: '#9A3412' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9A3412" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M12 3.5L21.5 20h-19z" />
                  <path d="M12 10v4.5" />
                  <path d="M12 17.5h.01" />
                </svg>
                <span>Flagged · {detail.flags.length} {detail.flags.length === 1 ? 'reason' : 'reasons'} to check</span>
              </div>
              <ul style={{ margin: 0, padding: '0 0 0 24px', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
                {detail.flags.map((f) => (
                  <li key={f.code} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ fontSize: 14, fontWeight: 500, color: '#7C2D12' }}>{f.message}</span>
                    <span style={{ fontSize: 13, lineHeight: 1.45, color: '#9A3412' }}>
                      {f.code === 'PRICE_ABOVE_REF' && detail.quoted_unit_price_idr != null && detail.reference_unit_price_idr != null && detail.diff_pct != null
                        ? `Rp ${formatRupiah(detail.quoted_unit_price_idr)} quoted vs Rp ${formatRupiah(detail.reference_unit_price_idr)} reference (${formatPct(detail.diff_pct)})`
                        : f.code === 'STOCK_COVER_HIGH' && detail.qty_on_hand != null && detail.avg_monthly_use != null
                        ? `${detail.qty_on_hand} ${detail.unit ?? ''} on hand, about ${detail.avg_monthly_use} ${detail.unit ?? ''} used per month`.trim()
                        : f.code === 'QTY_UNUSUAL' && detail.qty != null && detail.usual_qty != null
                        ? `${detail.qty} ${detail.unit ?? ''} requested, usually about ${detail.usual_qty}`.trim()
                        : f.code === 'NEW_SUPPLIER' && detail.quoting_supplier_name
                        ? `${detail.quoting_supplier_name} has no purchases in history`
                        : null}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Data grid */}
          <dl style={{
            margin: 0,
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: '14px 16px',
            fontSize: 14,
          }}>
            <div>
              <dt style={{ fontSize: 12, color: '#6B6B66' }}>Quoted total</dt>
              <dd style={{ margin: '2px 0 0', fontFamily: "'Geist Mono', monospace" }}>
                {detail.quoted_total_idr != null ? formatRupiahWithPrefix(detail.quoted_total_idr) : '—'}
              </dd>
            </div>
            <div>
              <dt style={{ fontSize: 12, color: '#6B6B66' }}>At reference price</dt>
              <dd style={{ margin: '2px 0 0', fontFamily: "'Geist Mono', monospace", display: 'flex', alignItems: 'center' }}>
                {detail.reference_total_idr != null ? formatRupiahWithPrefix(detail.reference_total_idr) : '—'}
                {detail.price_status && detail.price_status !== 'UNKNOWN' && (() => {
                  const styles = {
                    'WAJAR': { bg: '#E7F4EC', text: '#166534' },
                    'PERHATIAN': { bg: '#FFF4EC', text: '#9A3412' },
                    'TIDAK WAJAR': { bg: '#FDEBDD', text: '#9A3412' },
                  }
                  const style = styles[detail.price_status as keyof typeof styles]
                  return style ? (
                    <span style={{
                      marginLeft: 8,
                      padding: '2px 6px',
                      fontSize: 12,
                      borderRadius: 4,
                      background: style.bg,
                      color: style.text,
                      fontFamily: 'inherit',
                      fontWeight: 500,
                    }}>
                      {detail.price_status}
                    </span>
                  ) : null
                })()}
              </dd>
            </div>
            <div>
              <dt style={{ fontSize: 12, color: '#6B6B66' }}>Over reference</dt>
              <dd style={{
                margin: '2px 0 0',
                fontFamily: "'Geist Mono', monospace",
                color: detail.over_reference_idr != null && detail.over_reference_idr > 0 ? '#9A3412' : undefined,
                fontWeight: detail.over_reference_idr != null && detail.over_reference_idr > 0 ? 500 : undefined,
                display: 'flex',
                alignItems: 'center',
              }}>
                {detail.over_reference_idr != null ? formatRupiahWithPrefix(detail.over_reference_idr) : '—'}
                {detail.price_status && detail.price_status !== 'UNKNOWN' && (() => {
                  const styles = {
                    'WAJAR': { bg: '#E7F4EC', text: '#166534' },
                    'PERHATIAN': { bg: '#FFF4EC', text: '#9A3412' },
                    'TIDAK WAJAR': { bg: '#FDEBDD', text: '#9A3412' },
                  }
                  const style = styles[detail.price_status as keyof typeof styles]
                  return style ? (
                    <span style={{
                      marginLeft: 8,
                      padding: '2px 6px',
                      fontSize: 12,
                      borderRadius: 4,
                      background: style.bg,
                      color: style.text,
                      fontFamily: 'inherit',
                      fontWeight: 500,
                    }}>
                      {detail.price_status}
                    </span>
                  ) : null
                })()}
              </dd>
            </div>
            <div>
              <dt style={{ fontSize: 12, color: '#6B6B66' }}>Quoting supplier</dt>
              <dd style={{ margin: '2px 0 0' }}>{detail.quoting_supplier_name ?? '—'}</dd>
            </div>
            <div>
              <dt style={{ fontSize: 12, color: '#6B6B66' }}>Stock on record</dt>
              <dd style={{ margin: '2px 0 0', fontFamily: "'Geist Mono', monospace" }}>
                {detail.qty_on_hand != null ? `${detail.qty_on_hand} ${detail.unit ?? ''}`.trim() : '—'}
              </dd>
            </div>
            <div>
              <dt style={{ fontSize: 12, color: '#6B6B66' }}>Avg. monthly use</dt>
              <dd style={{ margin: '2px 0 0', fontFamily: "'Geist Mono', monospace" }}>
                {detail.avg_monthly_use != null ? `${detail.avg_monthly_use} ${detail.unit ?? ''}`.trim() : '—'}
              </dd>
            </div>
          </dl>

          {/* Status chip */}
          <div>
            <StatusChip status={detail.status} />
          </div>

          {/* Risk score */}
          {(() => {
            const score = detail.risk_score
            const color = score >= 50
              ? { fg: '#9A3412', bg: '#FDEBDD' }
              : score >= 20
                ? { fg: '#9A3412', bg: '#FFF4EC' }
                : { fg: '#166534', bg: '#E7F4EC' }
            return (
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  alignSelf: 'flex-start',
                  padding: '6px 12px',
                  borderRadius: 8,
                  background: color.bg,
                  color: color.fg,
                  fontSize: 13,
                  fontWeight: 500,
                }}
              >
                Risk Score:{' '}
                <span style={{ fontFamily: "'Geist Mono', monospace", fontVariantNumeric: 'tabular-nums' }}>
                  {score}/100
                </span>
              </div>
            )
          })()}

          {/* Return note (when returned) */}
          {detail.status === 'returned' && detail.actions.length > 0 && (() => {
            const returnAction = [...detail.actions].reverse().find(a => a.action === 'return')
            return returnAction?.note ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontSize: 12, color: '#6B6B66' }}>Return note</span>
                <p style={{ margin: 0, fontSize: 14, color: '#4A4A46' }}>{returnAction.note}</p>
              </div>
            ) : null
          })()}

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => setSupplierPanelOpen(true)}
              style={{
                height: 44,
                padding: '0 16px',
                border: 0,
                borderRadius: 10,
                background: '#1A1A1A',
                color: '#FFFFFF',
                font: 'inherit',
                fontSize: 14,
                cursor: 'pointer',
              }}
            >
              Compare suppliers
            </button>

            {canAct && role === 'owner' && (
              <>
                <button
                  type="button"
                  onClick={handleApprove}
                  disabled={approveMutation.isPending}
                  style={{
                    height: 44,
                    padding: '0 16px',
                    border: '1px solid #E0E0DB',
                    borderRadius: 10,
                    background: '#FFFFFF',
                    font: 'inherit',
                    fontSize: 14,
                    cursor: approveMutation.isPending ? 'not-allowed' : 'pointer',
                    color: approveMutation.isPending ? '#9E9E99' : '#1A1A1A',
                  }}
                >
                  {approveMutation.isPending ? 'Approving…' : 'Approve'}
                </button>
                <button
                  type="button"
                  onClick={() => setReturnDialogOpen(true)}
                  disabled={returnMutation.isPending}
                  style={{
                    height: 44,
                    padding: '0 16px',
                    border: '1px solid #E0E0DB',
                    borderRadius: 10,
                    background: '#FFFFFF',
                    font: 'inherit',
                    fontSize: 14,
                    cursor: returnMutation.isPending ? 'not-allowed' : 'pointer',
                    color: returnMutation.isPending ? '#9E9E99' : '#1A1A1A',
                  }}
                >
                  Return to requester
                </button>
              </>
            )}
            {canAct && role !== 'owner' && role != null && (
              <span style={{ fontSize: 13, color: '#9E9E99', fontStyle: 'italic' }}>
                Waiting for approval
              </span>
            )}

            {canRecheck && (
              <button
                type="button"
                disabled={rechecking}
                onClick={() => {
                  setRechecking(true)
                  void fetchWithAuth(`/api/request-items/${detail.id}/recheck`, { method: 'POST' })
                    .then(() => Promise.all([
                      qc.invalidateQueries({ queryKey: ['request-item', detail.id] }),
                      qc.invalidateQueries({ queryKey: ['queue'] }),
                    ]))
                    .finally(() => setRechecking(false))
                }}
                style={{
                  height: 44,
                  padding: '0 16px',
                  border: '1px solid #E0E0DB',
                  borderRadius: 10,
                  background: '#FFFFFF',
                  font: 'inherit',
                  fontSize: 14,
                  cursor: rechecking ? 'not-allowed' : 'pointer',
                  color: rechecking ? '#9E9E99' : '#1A1A1A',
                }}
              >
                {rechecking ? 'Rechecking…' : 'Recheck'}
              </button>
            )}
          </div>
        </div>

        {/* Right half */}
        <div style={{
          flex: '999 1 460px',
          minWidth: 0,
          boxSizing: 'border-box',
          padding: 24,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}>
          {rightTitle && (
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 500 }}>{rightTitle}</h3>
          )}
          {hasHistory && (
            <HistoryTable
              purchases={detail.last_purchases!}
              referencePrice={detail.reference_unit_price_idr}
            />
          )}
          {!hasHistory && hasWebQuotes && (
            <WebQuotesTable
              quotes={detail.web_quotes!}
              referencePrice={detail.reference_unit_price_idr}
            />
          )}
          {(hasHistory || !hasWebQuotes) && (
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#6B6B66' }}>
              All prices in Rp.
            </p>
          )}
        </div>

      </section>

      {/* Supplier comparison panel */}
      {supplierPanelOpen && (
        <SupplierPanel
          itemId={isNewItem ? null : detail.catalog_item_id}
          quotingSupplierName={detail.quoting_supplier_name}
          webQuotes={detail.web_quotes}
          onClose={() => setSupplierPanelOpen(false)}
        />
      )}

      {/* Return dialog */}
      {returnDialogOpen && (
        <ReturnDialog
          itemName={detail.raw_name}
          onConfirm={handleReturnConfirm}
          onCancel={() => setReturnDialogOpen(false)}
          isSending={returnMutation.isPending}
        />
      )}
    </>
  )
}

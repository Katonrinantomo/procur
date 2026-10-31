/**
 * VendorQuotesPage — upload a vendor quotation (PDF/XLSX), see each line's
 * price band, reference source, evidence links and recommendation, and the
 * vendor score.  Every band, recommendation and score is computed by the
 * backend (pricing.py); this page only displays them.
 */
import { Fragment, useRef, useState } from 'react'
import BandChip from './BandChip'
import { formatDate, formatPct, formatRupiah } from '../lib/format'
import {
  useQuotation,
  useQuotations,
  useQuotationToQueue,
  useUploadQuotation,
} from '../hooks/useQuotation'
import type { Quotation, QuotationLine } from '../types/api'

const MAX_MB = 10

const mono: React.CSSProperties = {
  fontFamily: "'Geist Mono', monospace",
  fontVariantNumeric: 'tabular-nums',
}

const panel: React.CSSProperties = {
  border: '1px solid #E6E6E2',
  borderRadius: 12,
}

const cell: React.CSSProperties = { padding: '13px 16px', verticalAlign: 'top' }
const numCell: React.CSSProperties = { ...cell, ...mono, textAlign: 'right', whiteSpace: 'nowrap' }

const secondaryBtn: React.CSSProperties = {
  height: 44,
  padding: '0 16px',
  border: '1px solid #E0E0DB',
  borderRadius: 10,
  background: '#FFFFFF',
  color: '#1A1A1A',
  font: 'inherit',
  fontSize: 14,
  cursor: 'pointer',
}

function primaryBtn(enabled: boolean): React.CSSProperties {
  return {
    height: 44,
    padding: '0 20px',
    border: 0,
    borderRadius: 10,
    background: enabled ? '#1A1A1A' : '#B0B0AB',
    color: '#FFFFFF',
    font: 'inherit',
    fontSize: 14,
    fontWeight: 500,
    cursor: enabled ? 'pointer' : 'not-allowed',
  }
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" style={{
      padding: '12px 16px',
      border: '1px solid #F2C7A5',
      background: '#FFF4EC',
      borderRadius: 8,
      color: '#7C2D12',
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      fontSize: 14,
    }}>
      <span style={{ flex: 1 }}>{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} style={{ ...secondaryBtn, height: 36, fontSize: 13 }}>
          Retry
        </button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Score card
// ---------------------------------------------------------------------------

function ScoreCard({ q }: { q: Quotation }) {
  const dropped = Object.entries(q.dropped_summary)
  return (
    <section aria-label="Vendor score" style={{ ...panel, padding: 24, display: 'flex', gap: 40, flexWrap: 'wrap' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 160 }}>
        <span style={{ fontSize: 12, color: '#6B6B66' }}>Vendor score</span>
        {q.vendor_score !== null ? (
          <span style={{ ...mono, fontSize: 40, fontWeight: 600, lineHeight: 1.1 }}>
            {q.vendor_score}
            <span style={{ fontSize: 16, color: '#6B6B66', fontWeight: 400 }}> / 100</span>
          </span>
        ) : (
          <span style={{ fontSize: 16, fontWeight: 500, color: '#3F3F3B', paddingTop: 10 }}>data tidak cukup</span>
        )}
      </div>
      <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px 32px', flex: 1 }}>
        <div>
          <dt style={{ fontSize: 12, color: '#6B6B66' }}>Price (80%)</dt>
          <dd style={{ margin: '2px 0 0', ...mono }}>
            {q.price_points !== null ? `${q.price_points.toFixed(1)} poin` : '—'}
          </dd>
        </div>
        <div>
          <dt style={{ fontSize: 12, color: '#6B6B66' }}>Arithmetic (20%)</dt>
          <dd style={{ margin: '2px 0 0', color: q.arithmetic_ok ? '#166534' : '#9A3412', fontWeight: 500 }}>
            {q.arithmetic_ok ? 'Aritmetika cocok' : 'Aritmetika tidak cocok'}
          </dd>
        </div>
        <div>
          <dt style={{ fontSize: 12, color: '#6B6B66' }}>Coverage</dt>
          <dd style={{ margin: '2px 0 0' }}>
            <span style={mono}>{q.covered_lines}</span> dari <span style={mono}>{q.total_lines}</span> baris punya pembanding
          </dd>
        </div>
        <div>
          <dt style={{ fontSize: 12, color: '#6B6B66' }}>Quotation total</dt>
          <dd style={{ margin: '2px 0 0', ...mono }}>
            {q.quote_total_idr !== null ? `Rp ${formatRupiah(q.quote_total_idr)}` : '—'}
          </dd>
        </div>
      </dl>
      {dropped.length > 0 && (
        <p style={{ margin: 0, width: '100%', fontSize: 13, color: '#4A4A46' }}>
          {dropped.map(([label, n]) => (
            <span key={label} style={{ marginRight: 16 }}>
              <span style={mono}>{n}</span> harga dibuang: {label}
            </span>
          ))}
        </p>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Lines table
// ---------------------------------------------------------------------------

function sourceText(line: QuotationLine): string {
  if (line.reference_source === 'history') return `History · ${line.history_count ?? 0} buys`
  if (line.reference_source === 'web') return `Web · ${line.evidence.length} quotes`
  return 'None'
}

function EvidenceRow({ line }: { line: QuotationLine }) {
  return (
    <tr>
      <td colSpan={9} style={{ padding: '0 16px 16px 48px', borderBottom: '1px solid #EDEDEA' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13 }}>
          {line.evidence.length === 0 && (
            <span style={{ color: '#6B6B66' }}>No marketplace listing passed the evidence check.</span>
          )}
          {line.evidence.map((e, i) => (
            <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
              <span style={{ color: '#4A4A46', minWidth: 120 }}>{e.seller ?? '—'}</span>
              {e.url ? (
                <a href={e.url} target="_blank" rel="noopener noreferrer" style={{ color: '#1E3A8A', flex: 1 }}>
                  {e.title ?? e.url}
                </a>
              ) : (
                <span style={{ flex: 1 }}>{e.title ?? '—'}</span>
              )}
              {e.match === 'close' && <span style={{ color: '#6B6B66' }}>mirip</span>}
              {e.pack_qty !== null && e.listing_price_idr !== null && (
                <span style={{ color: '#6B6B66' }}>
                  <span style={mono}>{formatRupiah(e.listing_price_idr)}</span> / isi <span style={mono}>{e.pack_qty}</span>
                </span>
              )}
              <span style={mono}>{formatRupiah(e.price_idr)}</span>
            </div>
          ))}
          {line.dropped.map((d, i) => (
            <div key={`d${i}`} style={{ display: 'flex', gap: 12, alignItems: 'baseline', color: '#6B6B66' }}>
              <span style={{ minWidth: 120 }}>Dibuang</span>
              <span style={{ flex: 1, textDecoration: 'line-through' }}>{d.title ?? d.url ?? '—'}</span>
              <span>{d.reason_label}</span>
              <span style={mono}>{d.price_idr !== null ? formatRupiah(d.price_idr) : '—'}</span>
            </div>
          ))}
        </div>
      </td>
    </tr>
  )
}

function LinesTable({ lines }: { lines: QuotationLine[] }) {
  const [open, setOpen] = useState<Set<number>>(new Set())

  function toggle(n: number) {
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(n)) next.delete(n)
      else next.add(n)
      return next
    })
  }

  return (
    <div style={{ ...panel, overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 1040 }}>
        <thead>
          <tr style={{ background: '#F7F7F5', textAlign: 'left', fontSize: 12, color: '#5E5E59' }}>
            {['#', 'Item', 'Qty', 'Quoted / unit', 'Reference / unit', 'Diff.', 'Reference source', 'Band', 'Recommendation'].map((col) => (
              <th
                key={col}
                style={{
                  padding: '11px 16px',
                  fontWeight: 500,
                  textAlign: ['Qty', 'Quoted / unit', 'Reference / unit', 'Diff.'].includes(col) ? 'right' : 'left',
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => {
            const isOpen = open.has(line.line_no)
            const hasDetail = line.evidence.length > 0 || line.dropped.length > 0
            const flagged = line.band === 'TIDAK WAJAR'
            return (
              <Fragment key={line.line_no}>
                <tr style={{
                  borderBottom: isOpen ? 'none' : '1px solid #EDEDEA',
                  background: flagged ? '#FFF8F2' : undefined,
                  boxShadow: flagged ? 'inset 3px 0 0 #9A3412' : undefined,
                }}>
                  <td style={{ ...cell, ...mono, color: '#6B6B66' }}>{String(line.line_no).padStart(2, '0')}</td>
                  <td style={cell}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <span>{line.name}</span>
                      {hasDetail && (
                        <button
                          type="button"
                          aria-expanded={isOpen}
                          onClick={() => toggle(line.line_no)}
                          style={{
                            alignSelf: 'flex-start',
                            minHeight: 28,
                            padding: 0,
                            border: 0,
                            background: 'transparent',
                            color: '#1E3A8A',
                            font: 'inherit',
                            fontSize: 12,
                            cursor: 'pointer',
                          }}
                        >
                          {isOpen ? 'Hide links' : `Links (${line.evidence.length})`}
                        </button>
                      )}
                    </div>
                  </td>
                  <td style={numCell}>{line.qty !== null ? `${formatRupiah(line.qty)} ${line.unit ?? ''}` : '—'}</td>
                  <td style={numCell}>{line.unit_price_idr !== null ? formatRupiah(line.unit_price_idr) : '—'}</td>
                  <td style={numCell}>
                    {line.reference_unit_price_idr !== null ? formatRupiah(line.reference_unit_price_idr) : '—'}
                  </td>
                  <td style={{ ...numCell, color: flagged ? '#9A3412' : undefined, fontWeight: flagged ? 500 : undefined }}>
                    {line.diff_pct !== null ? formatPct(line.diff_pct) : '—'}
                  </td>
                  <td style={{ ...cell, color: '#4A4A46' }}>{sourceText(line)}</td>
                  <td style={cell}><BandChip value={line.band} /></td>
                  <td style={cell}>{line.recommendation ? <BandChip value={line.recommendation} /> : '—'}</td>
                </tr>
                {isOpen && <EvidenceRow line={line} />}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function VendorQuotesPage() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const upload = useUploadQuotation()
  const toQueue = useQuotationToQueue()
  const list = useQuotations()
  const detail = useQuotation(selectedId)
  const q = detail.data

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null
    setFileError(null)
    if (f && f.size > MAX_MB * 1024 * 1024) {
      setFile(null)
      setFileError(`File is larger than ${MAX_MB} MB.`)
      return
    }
    setFile(f)
  }

  function handleUpload() {
    if (!file) return
    upload.mutate(file, { onSuccess: (res) => setSelectedId(res.id) })
  }

  return (
    <main style={{
      width: '100%',
      maxWidth: 1240,
      margin: '0 auto',
      boxSizing: 'border-box',
      padding: '28px 28px 40px',
      display: 'flex',
      flexDirection: 'column',
      gap: 28,
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Vendor quotes</h1>
        <span style={{ fontSize: 13, color: '#6B6B66' }}>
          Upload a quotation (.pdf or .xlsx, up to {MAX_MB} MB). Each line is compared with purchase history or marketplace prices.
        </span>
      </div>

      {/* Upload + recent */}
      <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <section aria-label="Upload quotation" style={{ ...panel, padding: 24, display: 'flex', flexDirection: 'column', gap: 16, flex: '1 1 420px' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.xlsx,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <button type="button" onClick={() => inputRef.current?.click()} style={secondaryBtn}>
              Choose file
            </button>
            <span style={{ fontSize: 13, color: file ? '#1A1A1A' : '#6B6B66' }}>
              {file ? file.name : 'No file chosen'}
            </span>
          </div>
          <button
            type="button"
            disabled={!file || upload.isPending}
            onClick={handleUpload}
            style={{ ...primaryBtn(!!file && !upload.isPending), alignSelf: 'flex-start' }}
          >
            {upload.isPending ? 'Checking…' : 'Check quotation'}
          </button>
          {fileError && <ErrorBanner message={fileError} />}
          {upload.isError && <ErrorBanner message={upload.error.message} onRetry={handleUpload} />}
        </section>

        <section aria-label="Recent quotations" style={{ ...panel, flex: '1 1 320px', overflow: 'hidden' }}>
          <div style={{ padding: '11px 16px', background: '#F7F7F5', fontSize: 12, color: '#5E5E59', fontWeight: 500 }}>
            Recent quotations
          </div>
          {list.isError && <div style={{ padding: 16 }}><ErrorBanner message={list.error.message} onRetry={() => void list.refetch()} /></div>}
          {list.data?.length === 0 && (
            <p style={{ margin: 0, padding: 16, fontSize: 13, color: '#6B6B66' }}>No quotations yet.</p>
          )}
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {list.data?.map((item) => (
              <li key={item.id} style={{ borderTop: '1px solid #EDEDEA' }}>
                <button
                  type="button"
                  onClick={() => setSelectedId(item.id)}
                  style={{
                    width: '100%',
                    minHeight: 44,
                    padding: '8px 16px',
                    border: 0,
                    background: item.id === selectedId ? '#F2F2EF' : 'transparent',
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 12,
                    font: 'inherit',
                    fontSize: 13,
                    textAlign: 'left',
                    cursor: 'pointer',
                  }}
                >
                  <span>{item.vendor_name ?? item.filename}</span>
                  <span style={{ ...mono, color: '#6B6B66' }}>
                    {item.vendor_score !== null ? item.vendor_score : item.status} · {formatDate(item.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {detail.isError && <ErrorBanner message={detail.error.message} onRetry={() => void detail.refetch()} />}

      {q && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>{q.vendor_name ?? 'Unknown vendor'}</h2>
              <span style={{ fontSize: 13, color: '#6B6B66' }}>
                {[q.quote_no && <span key="no" style={mono}>{q.quote_no}</span>,
                  q.quote_date && formatDate(q.quote_date),
                  q.filename]
                  .filter(Boolean)
                  .map((part, i) => <Fragment key={i}>{i > 0 && ' · '}{part}</Fragment>)}
              </span>
            </div>
            {q.status === 'checked' && q.request_id === null && (
              <button
                type="button"
                disabled={toQueue.isPending}
                onClick={() => toQueue.mutate(q.id)}
                style={secondaryBtn}
              >
                {toQueue.isPending ? 'Adding…' : "Add to today's queue"}
              </button>
            )}
            {q.request_id !== null && (
              <span style={{ fontSize: 14, color: '#166534' }}>
                Sudah masuk antrean · <a href="#today" style={{ color: '#1A1A1A' }}>Open Today</a>
              </span>
            )}
          </div>

          {toQueue.isError && <ErrorBanner message={toQueue.error.message} />}

          {q.status === 'pending' || q.status === 'unreadable' ? (
            <ErrorBanner message={q.check_error ?? 'Penawaran belum bisa dicek.'} />
          ) : (
            <>
              <ScoreCard q={q} />
              <LinesTable lines={q.lines} />
            </>
          )}
        </>
      )}
    </main>
  )
}

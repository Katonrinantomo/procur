/**
 * QuickCheckPage — instant dry-run price check for a single item line.
 * Matches design/quick-check.html exactly.
 */
import { useState } from 'react'
import StatusChip from './StatusChip'
import { formatRupiah, formatRupiahWithPrefix, formatPct, formatDate } from '../lib/format'
import type { QuickCheckResult } from '../types/api'

const EXAMPLE_CHIPS = [
  'bearing 6205 ZZ 20 pcs @38.500',
  'solenoid valve 24V DC 1/2" 2 pcs',
  'lakban bening 48mm 3 dus @210rb',
]

// ---------------------------------------------------------------------------
// Flag box (reused from Inspector.tsx pattern)
// ---------------------------------------------------------------------------

function FlagBox({ result }: { result: QuickCheckResult }) {
  if (result.flags.length === 0) {
    return (
      <span style={{
        display: 'inline-block',
        fontSize: 12,
        fontWeight: 500,
        padding: '4px 8px',
        borderRadius: 6,
        color: '#3F3F3B',
        background: '#F0F0EC',
      }}>
        Looks normal
      </span>
    )
  }
  return (
    <div style={{
      border: '1px solid #F2C7A5',
      background: '#FFF4EC',
      borderRadius: 10,
      padding: '14px 16px',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, fontWeight: 600, color: '#9A3412' }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9A3412" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 3.5L21.5 20h-19z" />
          <path d="M12 10v4.5" />
          <path d="M12 17.5h.01" />
        </svg>
        <span>Flagged · {result.flags.length} {result.flags.length === 1 ? 'reason' : 'reasons'} to check</span>
      </div>
      <ul style={{ margin: 0, padding: '0 0 0 24px', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {result.flags.map((f) => (
          <li key={f.code} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontSize: 14, fontWeight: 500, color: '#7C2D12' }}>{f.message}</span>
            <span style={{ fontSize: 13, lineHeight: 1.45, color: '#9A3412' }}>
              {f.code === 'PRICE_ABOVE_REF' && result.quoted_unit_price_idr != null && result.reference_unit_price_idr != null && result.diff_pct != null
                ? `Rp ${formatRupiah(result.quoted_unit_price_idr)} quoted vs Rp ${formatRupiah(result.reference_unit_price_idr)} reference (${formatPct(result.diff_pct)})`
                : f.code === 'NEW_SUPPLIER' && result.quoting_supplier_name
                ? `${result.quoting_supplier_name} has no purchases in history`
                : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Check row narrative
// ---------------------------------------------------------------------------

function buildCheckNarrative(result: QuickCheckResult): string {
  if (result.checked_via === 'history' && result.last_purchases.length > 0) {
    // Tally suppliers
    const tally: Record<string, number> = {}
    for (const p of result.last_purchases) {
      tally[p.supplier_name] = (tally[p.supplier_name] ?? 0) + 1
    }
    const supplierText = Object.entries(tally)
      .sort((a, b) => b[1] - a[1])
      .map(([name, cnt]) => (cnt > 1 ? `${name} ×${cnt}` : name))
      .join(', ')
    const lastDate = formatDate(result.last_purchases[0].purchase_date)
    const refStr = result.reference_unit_price_idr != null
      ? `Rp ${formatRupiah(result.reference_unit_price_idr)}`
      : '—'
    return `Last ${result.history_count} buys averaged ${refStr} (${supplierText}). Last bought ${lastDate}.`
  }
  if (result.checked_via === 'web' && result.web_quotes.length > 0) {
    const refStr = result.reference_unit_price_idr != null
      ? `Rp ${formatRupiah(result.reference_unit_price_idr)}`
      : '—'
    const mostRecent = result.web_quotes.reduce((a, b) =>
      new Date(a.fetched_at) > new Date(b.fetched_at) ? a : b
    )
    return `Web median ${refStr} from ${result.web_quotes.length} quote${result.web_quotes.length !== 1 ? 's' : ''}. Data from ${formatDate(mostRecent.fetched_at)}.`
  }
  return 'No price reference found.'
}

// ---------------------------------------------------------------------------
// Single result card
// ---------------------------------------------------------------------------

interface ResultCardProps {
  result: QuickCheckResult
}

function ResultCard({ result }: ResultCardProps) {
  const [addState, setAddState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [addError, setAddError] = useState<string | null>(null)

  async function handleAddToQueue() {
    setAddState('loading')
    setAddError(null)
    try {
      const res = await fetch('/api/requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requested_by: 'Quick check',
          items: [{
            line_no: 1,
            raw_name: result.raw_name,
            department: result.department ?? undefined,
            qty: result.qty ?? undefined,
            unit: result.unit ?? undefined,
            quoted_unit_price_idr: result.quoted_unit_price_idr ?? undefined,
            quoting_supplier_name: result.quoting_supplier_name ?? undefined,
          }],
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error((data as { detail?: string }).detail ?? `HTTP ${res.status}`)
      }
      setAddState('done')
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Unknown error')
      setAddState('error')
    }
  }

  const headerLabel = result.history_count > 0
    ? `Bought ${result.history_count} time${result.history_count !== 1 ? 's' : ''} before`
    : 'New item'

  const checkNarrative = buildCheckNarrative(result)

  return (
    <article style={{
      width: '100%',
      boxSizing: 'border-box',
      border: '1px solid #E6E6E2',
      borderRadius: 12,
      padding: 24,
      display: 'flex',
      flexDirection: 'column',
      gap: 20,
    }}>
      {/* Card header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#6B6B66' }}>{headerLabel}</span>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{result.name}</h2>
        </div>
        <StatusChip status={result.status} />
      </div>

      {/* Data rows */}
      <dl style={{ margin: 0, display: 'flex', flexDirection: 'column' }}>
        {/* Organize row */}
        <div style={{ display: 'flex', gap: 16, padding: '14px 0', borderTop: '1px solid #EDEDEA', flexWrap: 'wrap' }}>
          <dt style={{ width: 80, flexShrink: 0, fontSize: 13, color: '#6B6B66', paddingTop: 1 }}>Organize</dt>
          <dd style={{ margin: 0, flex: '1 1 320px', minWidth: 0, fontSize: 14, lineHeight: 1.55 }}>
            {[
              result.category ? result.category.charAt(0).toUpperCase() + result.category.slice(1).toLowerCase() : result.category,
              result.qty != null && result.unit ? `${result.qty} ${result.unit}` : null,
              result.quoted_unit_price_idr != null
                ? <><span style={{ fontFamily: "'Geist Mono', monospace", fontVariantNumeric: 'tabular-nums' }}>{formatRupiahWithPrefix(result.quoted_unit_price_idr)}</span>{' per ' + (result.unit ?? 'unit')}</>
                : null,
              result.quoting_supplier_name ? `quoted by ${result.quoting_supplier_name}` : null,
            ]
              .filter(Boolean)
              .reduce<React.ReactNode[]>((acc, part, i) => {
                if (i > 0) acc.push(' · ')
                acc.push(part)
                return acc
              }, [])}
          </dd>
        </div>

        {/* Check row */}
        <div style={{ display: 'flex', gap: 16, padding: '14px 0', borderTop: '1px solid #EDEDEA', flexWrap: 'wrap' }}>
          <dt style={{ width: 80, flexShrink: 0, fontSize: 13, color: '#6B6B66', paddingTop: 1 }}>Check</dt>
          <dd style={{ margin: 0, flex: '1 1 320px', minWidth: 0, fontSize: 14, lineHeight: 1.55 }}>
            {result.reference_unit_price_idr != null
              ? checkNarrative.replace(
                  `Rp ${formatRupiah(result.reference_unit_price_idr)}`,
                  '\u0000'  // placeholder replaced below
                ).split('\u0000').reduce<React.ReactNode[]>((acc, part, i, arr) => {
                  acc.push(part)
                  if (i < arr.length - 1) {
                    acc.push(
                      <span key={i} style={{ fontFamily: "'Geist Mono', monospace", fontVariantNumeric: 'tabular-nums' }}>
                        {formatRupiahWithPrefix(result.reference_unit_price_idr!)}
                      </span>
                    )
                  }
                  return acc
                }, [])
              : checkNarrative}
          </dd>
        </div>

        {/* Mark row */}
        <div style={{ display: 'flex', gap: 16, padding: '14px 0', borderTop: '1px solid #EDEDEA', flexWrap: 'wrap' }}>
          <dt style={{ width: 80, flexShrink: 0, fontSize: 13, color: '#6B6B66', paddingTop: 1 }}>Mark</dt>
          <dd style={{ margin: 0, flex: '1 1 320px', minWidth: 0 }}>
            <FlagBox result={result} />
          </dd>
        </div>
      </dl>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        {addState === 'done' ? (
          <a
            href="#today"
            onClick={() => { window.location.hash = '#today' }}
            style={{
              height: 44,
              padding: '0 18px',
              border: 0,
              borderRadius: 10,
              background: '#1A1A1A',
              color: '#FFFFFF',
              font: 'inherit',
              fontSize: 14,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              textDecoration: 'none',
            }}
          >
            View in Today →
          </a>
        ) : (
          <button
            type="button"
            disabled={addState === 'loading'}
            onClick={() => { void handleAddToQueue() }}
            style={{
              height: 44,
              padding: '0 18px',
              border: 0,
              borderRadius: 10,
              background: '#1A1A1A',
              color: '#FFFFFF',
              font: 'inherit',
              fontSize: 14,
              cursor: addState === 'loading' ? 'default' : 'pointer',
              opacity: addState === 'loading' ? 0.6 : 1,
            }}
          >
            {addState === 'loading' ? 'Adding…' : "Add to today's queue"}
          </button>
        )}
        <button
          type="button"
          onClick={() => { window.location.hash = '#history' }}
          style={{
            height: 44,
            padding: '0 18px',
            border: '1px solid #E0E0DB',
            borderRadius: 10,
            background: '#FFFFFF',
            font: 'inherit',
            fontSize: 14,
            cursor: 'pointer',
          }}
        >
          See purchase history
        </button>
        {addError && (
          <span style={{ fontSize: 13, color: '#9A3412' }}>{addError}</span>
        )}
      </div>
    </article>
  )
}

// ---------------------------------------------------------------------------
// Check error card
// ---------------------------------------------------------------------------

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div style={{
      width: '100%',
      boxSizing: 'border-box',
      border: '1px solid #F2C7A5',
      borderRadius: 12,
      padding: '20px 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 16,
      flexWrap: 'wrap',
    }}>
      <span style={{ fontSize: 14, color: '#9A3412' }}>{message}</span>
      <button
        type="button"
        onClick={onRetry}
        style={{
          height: 36,
          padding: '0 14px',
          border: '1px solid #9A3412',
          borderRadius: 8,
          background: 'transparent',
          color: '#9A3412',
          font: 'inherit',
          fontSize: 13,
          cursor: 'pointer',
        }}
      >
        Retry
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// QuickCheckPage
// ---------------------------------------------------------------------------

export default function QuickCheckPage() {
  const [inputValue, setInputValue] = useState('')
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [results, setResults] = useState<QuickCheckResult[]>([])
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [lastText, setLastText] = useState('')

  async function runCheck(text: string) {
    if (!text.trim()) return
    setState('loading')
    setErrorMsg(null)
    setLastText(text)
    try {
      const res = await fetch('/api/quick-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error((data as { detail?: string }).detail ?? `HTTP ${res.status}`)
      }
      const data: QuickCheckResult[] = await res.json()
      setResults(data)
      setState('done')
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Check failed')
      setState('error')
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    void runCheck(inputValue)
  }

  function handleRetry() {
    void runCheck(lastText)
  }

  return (
    <main style={{
      width: '100%',
      maxWidth: 760,
      margin: '0 auto',
      boxSizing: 'border-box',
      padding: '64px 28px 48px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 28,
    }}>
      {/* Hero text */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, textAlign: 'center' }}>
        <h1 style={{ margin: 0, fontSize: 32, fontWeight: 500, letterSpacing: '-0.02em' }}>
          What are you buying today?
        </h1>
        <p style={{ margin: 0, fontSize: 15, color: '#6B6B66' }}>
          Type one item the way it was asked. Nothing is saved until you add it to the queue.
        </p>
      </div>

      {/* Search form */}
      <form
        onSubmit={handleSubmit}
        style={{
          width: '100%',
          boxSizing: 'border-box',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          background: '#FFFFFF',
          border: '1px solid #E0E0DB',
          borderRadius: 999,
          padding: '8px 8px 8px 24px',
        }}
      >
        <label htmlFor="qc-input" style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>
          Item to check
        </label>
        <input
          id="qc-input"
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="e.g. oli hidrolik 46 20L 4 drum @1,45jt dari CV Sinar Pelumas"
          style={{
            flexGrow: 1,
            minWidth: 0,
            border: 0,
            outline: 'none',
            font: 'inherit',
            fontSize: 16,
            background: 'transparent',
            color: '#1A1A1A',
          }}
        />
        <button
          type="submit"
          disabled={state === 'loading'}
          style={{
            height: 44,
            padding: '0 22px',
            border: 0,
            borderRadius: 999,
            background: '#1A1A1A',
            color: '#FFFFFF',
            font: 'inherit',
            fontSize: 14,
            cursor: state === 'loading' ? 'default' : 'pointer',
            opacity: state === 'loading' ? 0.6 : 1,
            flexShrink: 0,
          }}
        >
          {state === 'loading' ? 'Checking…' : 'Check'}
        </button>
      </form>

      {/* Example chips */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', alignItems: 'center', fontSize: 13 }}>
        <span style={{ color: '#6B6B66' }}>Try</span>
        {EXAMPLE_CHIPS.map((chip) => (
          <button
            key={chip}
            type="button"
            onClick={() => setInputValue(chip)}
            style={{
              height: 36,
              padding: '0 14px',
              border: '1px solid #E0E0DB',
              borderRadius: 999,
              background: '#FFFFFF',
              font: 'inherit',
              fontSize: 13,
              color: '#4A4A46',
              cursor: 'pointer',
            }}
          >
            {chip}
          </button>
        ))}
      </div>

      {/* Loading indicator */}
      {state === 'loading' && (
        <p style={{ margin: 0, fontSize: 14, color: '#6B6B66' }}>Checking…</p>
      )}

      {/* Error state */}
      {state === 'error' && errorMsg && (
        <ErrorCard message={errorMsg} onRetry={handleRetry} />
      )}

      {/* Results */}
      {state === 'done' && results.map((result, i) => (
        <ResultCard key={i} result={result} />
      ))}
    </main>
  )
}

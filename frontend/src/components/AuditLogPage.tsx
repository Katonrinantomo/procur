import { useEffect, useState } from 'react'
import { fetchWithAuth } from '../lib/api'
import { formatDateTime } from '../lib/format'
import { OUTCOME_LABEL } from '../lib/decisions'
import type { DecisionRow } from '../types/api'

const PAGE: React.CSSProperties = {
  width: '100%',
  maxWidth: 1240,
  margin: '0 auto',
  boxSizing: 'border-box',
  padding: '28px 28px 40px',
  display: 'flex',
  flexDirection: 'column',
  gap: 24,
}

const DATE_INPUT: React.CSSProperties = {
  height: 36,
  padding: '0 10px',
  border: '1px solid #E0E0DB',
  borderRadius: 8,
  font: 'inherit',
  fontSize: 13,
  color: '#1A1A1A',
  background: '#FFFFFF',
}

const DECISION_LABEL: Record<string, string> = {
  approve: 'Approve',
  return: 'Return',
  pay: 'Pay',
  hold: 'Hold',
  clarify: 'Clarify',
}

function query(from: string, to: string): string {
  const params = new URLSearchParams()
  if (from) params.set('from', from)
  if (to) params.set('to', to)
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

async function errorText(res: Response): Promise<string> {
  const data = await res.json().catch(() => ({})) as { detail?: unknown }
  return typeof data.detail === 'string' ? data.detail : `HTTP ${res.status}`
}

export default function AuditLogPage() {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [rows, setRows] = useState<DecisionRow[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    async function load() {
      try {
        const res = await fetchWithAuth(`/api/decisions${query(from, to)}`)
        if (!res.ok) throw new Error(await errorText(res))
        const data = await res.json() as DecisionRow[]
        if (!cancelled) setRows(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => { cancelled = true }
  }, [from, to])

  // The CSV needs the auth header, so fetch it and hand the browser a blob.
  async function downloadCsv() {
    setExporting(true)
    try {
      const res = await fetchWithAuth(`/api/decisions.csv${query(from, to)}`)
      if (!res.ok) throw new Error(await errorText(res))
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `decisions_${from || 'all'}_${to || 'all'}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  return (
    <main style={PAGE}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#1A1A1A' }}>Audit Log</h1>
          <p style={{ margin: 0, fontSize: 14, color: '#6B6B66' }}>Every decision, who made it, why, and what they saw.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#6B6B66' }}>
            From
            <input type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} style={DATE_INPUT} />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#6B6B66' }}>
            To
            <input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} style={DATE_INPUT} />
          </label>
          <button
            type="button"
            onClick={() => { void downloadCsv() }}
            disabled={exporting}
            style={{
              height: 36,
              padding: '0 14px',
              border: '1px solid #E0E0DB',
              borderRadius: 8,
              background: '#FFFFFF',
              font: 'inherit',
              fontSize: 13,
              color: exporting ? '#9E9E99' : '#1A1A1A',
              cursor: exporting ? 'not-allowed' : 'pointer',
            }}
          >
            {exporting ? 'Exporting…' : 'Download CSV'}
          </button>
        </div>
      </div>

      {error && <p style={{ margin: 0, color: '#9A3412', fontSize: 14 }}>Error: {error}</p>}

      {loading && !rows && <p style={{ margin: 0, color: '#6B6B66', fontSize: 14 }}>Loading audit log…</p>}

      {rows && rows.length === 0 && !loading && (
        <p style={{ margin: 0, color: '#6B6B66', fontSize: 14 }}>No decisions in this period.</p>
      )}

      {rows && rows.length > 0 && (
        <div style={{ border: '1px solid #E6E6E2', borderRadius: 12, overflowX: 'auto', opacity: loading ? 0.6 : 1 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 980 }}>
            <thead>
              <tr style={{ background: '#F7F7F5', textAlign: 'left', fontSize: 12, color: '#5E5E59' }}>
                <th style={{ padding: '11px 16px', fontWeight: 500 }}>Waktu</th>
                <th style={{ padding: '11px 16px', fontWeight: 500 }}>User</th>
                <th style={{ padding: '11px 16px', fontWeight: 500 }}>Aksi</th>
                <th style={{ padding: '11px 16px', fontWeight: 500 }}>Nama Barang</th>
                <th style={{ padding: '11px 16px', fontWeight: 500 }}>Alasan</th>
                <th style={{ padding: '11px 16px', fontWeight: 500 }}>Outcome</th>
                <th style={{ padding: '11px 16px', fontWeight: 500, textAlign: 'right' }}>Risk</th>
                <th style={{ padding: '11px 16px', fontWeight: 500 }}>Flags</th>
              </tr>
            </thead>
            <tbody style={{ fontVariantNumeric: 'tabular-nums' }}>
              {rows.map((row) => (
                <tr key={row.id} style={{ borderTop: '1px solid #EDEDEA' }}>
                  <td style={{ padding: '11px 16px', whiteSpace: 'nowrap', fontFamily: "'Geist Mono', monospace", fontSize: 13 }}>
                    {formatDateTime(row.created_at)}
                  </td>
                  <td style={{ padding: '11px 16px' }}>
                    {row.username ?? '—'}
                    {row.role && <span style={{ color: '#6B6B66' }}> ({row.role})</span>}
                  </td>
                  <td style={{ padding: '11px 16px' }}>{DECISION_LABEL[row.decision] ?? row.decision}</td>
                  <td style={{ padding: '11px 16px' }}>{row.item_name ?? '—'}</td>
                  <td style={{ padding: '11px 16px', color: row.reason ? '#4A4A46' : '#9E9E99' }}>{row.reason ?? '—'}</td>
                  <td style={{ padding: '11px 16px', color: row.outcome_tag ? '#4A4A46' : '#9E9E99' }}>
                    {row.outcome_tag ? OUTCOME_LABEL[row.outcome_tag] : '—'}
                  </td>
                  <td style={{ padding: '11px 16px', textAlign: 'right', fontFamily: "'Geist Mono', monospace" }}>
                    {row.snapshot?.risk_score ?? '—'}
                  </td>
                  <td style={{ padding: '11px 16px', color: '#4A4A46', fontSize: 13 }}>
                    {row.snapshot?.flags && row.snapshot.flags.length > 0
                      ? row.snapshot.flags.map((f) => f.code).join(', ')
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  )
}

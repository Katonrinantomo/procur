import { useEffect, useState } from 'react'
import { fetchWithAuth } from '../lib/api'
import { formatDate } from '../lib/format'
import type { AuditLogRow } from '../types/api'

export default function AuditLogPage() {
  const [rows, setRows] = useState<AuditLogRow[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    async function load() {
      try {
        const res = await fetchWithAuth('/api/audit-logs')
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error((data as { detail?: string }).detail ?? `HTTP ${res.status}`)
        }
        const data = await res.json() as AuditLogRow[]
        if (!cancelled) setRows(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <main style={{ width: '100%', maxWidth: 1240, margin: '0 auto', boxSizing: 'border-box', padding: '28px 28px 40px' }}>
        <p style={{ color: '#6B6B66', fontSize: 14 }}>Loading audit log…</p>
      </main>
    )
  }

  if (error) {
    return (
      <main style={{ width: '100%', maxWidth: 1240, margin: '0 auto', boxSizing: 'border-box', padding: '28px 28px 40px' }}>
        <p style={{ color: '#9A3412', fontSize: 14 }}>Error: {error}</p>
      </main>
    )
  }

  if (!rows || rows.length === 0) {
    return (
      <main style={{ width: '100%', maxWidth: 1240, margin: '0 auto', boxSizing: 'border-box', padding: '28px 28px 40px' }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#1A1A1A' }}>Audit Log</h1>
        <p style={{ margin: '8px 0 0', color: '#6B6B66', fontSize: 14 }}>No audit entries yet.</p>
      </main>
    )
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
      gap: 24,
    }}>
      <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#1A1A1A' }}>Audit Log</h1>

      <div style={{ border: '1px solid #E6E6E2', borderRadius: 12, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 720 }}>
          <thead>
            <tr style={{ background: '#F7F7F5', textAlign: 'left', fontSize: 12, color: '#5E5E59' }}>
              <th style={{ padding: '11px 16px', fontWeight: 500 }}>Waktu</th>
              <th style={{ padding: '11px 16px', fontWeight: 500 }}>User</th>
              <th style={{ padding: '11px 16px', fontWeight: 500 }}>Aksi</th>
              <th style={{ padding: '11px 16px', fontWeight: 500 }}>Nama Barang</th>
              <th style={{ padding: '11px 16px', fontWeight: 500 }}>Catatan</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                style={{ borderTop: '1px solid #EDEDEA' }}
              >
                <td style={{ padding: '11px 16px', whiteSpace: 'nowrap' }}>{formatDate(row.created_at)}</td>
                <td style={{ padding: '11px 16px' }}>{row.actor_role}</td>
                <td style={{ padding: '11px 16px' }}>{row.action}</td>
                <td style={{ padding: '11px 16px' }}>{row.item_name ?? '—'}</td>
                <td style={{ padding: '11px 16px', color: row.note ? '#4A4A46' : '#9E9E99' }}>{row.note ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  )
}
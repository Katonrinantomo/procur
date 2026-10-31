import { useState, useEffect, useRef } from 'react'
import AppHeader from './components/AppHeader'
import QueueHeader from './components/QueueHeader'
import QueueTable from './components/QueueTable'
import Inspector from './components/Inspector'
import { SkeletonRows } from './components/SkeletonRow'
import AddRequestsDialog from './components/AddRequestsDialog'
import ImportPage from './components/ImportPage'
import HistoryPage from './components/HistoryPage'
import QuickCheckPage from './components/QuickCheckPage'
import AuditLogPage from './components/AuditLogPage'
import LoginPage from './components/LoginPage'
import LandingPage from './components/LandingPage'
import { useQueue } from './hooks/useQueue'
import { useRequestItem } from './hooks/useRequestItem'
import { useHash } from './hooks/useHash'
import { canAddRequests, canOpenHash, landingHash } from './lib/roles'
import type { QueueRow } from './types/api'

export default function App() {
  const [token] = useState<string | null>(
    () => localStorage.getItem('token')
  )
  // A 401 elsewhere sets auth_message and reloads; go straight to the login form.
  const [showLogin, setShowLogin] = useState(
    () => sessionStorage.getItem('auth_message') !== null
  )

  if (!token && !showLogin) {
    return <LandingPage onLoginClick={() => setShowLogin(true)} />
  }

  if (!token) {
    return (
      <LoginPage
        onLogin={(role) => {
          window.location.hash = landingHash(role)
          window.location.reload()
        }}
      />
    )
  }

  return <AuthedApp />
}

function AuthedApp() {
  const [role] = useState<string | null>(
    () => localStorage.getItem('role')
  )
  const [username] = useState<string | null>(
    () => localStorage.getItem('username')
  )

  const hash = useHash()
  const { data: queueData, isLoading: queueLoading, isError: queueError, refetch } = useQueue()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [activeFilter, setActiveFilter] = useState('All')
  const [dialogOpen, setDialogOpen] = useState(false)
  const addBtnRef = useRef<HTMLButtonElement>(null)

  // Send the user to their role's landing page when the hash is one they can't open.
  useEffect(() => {
    if (!canOpenHash(role, hash)) {
      window.location.hash = landingHash(role)
    }
  }, [role, hash])

  const { data: detail, isLoading: detailLoading } = useRequestItem(selectedId)

  // Auto-select first flagged row (or first row) on initial load
  useEffect(() => {
    if (!queueData || selectedId !== null) return
    const rows = queueData.rows
    const flagged = rows.find((r) => r.status === 'flagged')
    const first = flagged ?? rows[0]
    if (first) setSelectedId(first.id)
  }, [queueData, selectedId])

  // Filter rows based on active filter chip
  const filteredRows = queueData?.rows.filter((row) => {
    if (activeFilter === 'All') return true
    if (activeFilter === 'Flagged') return row.status === 'flagged'
    if (activeFilter === 'New') return row.status === 'new'
    if (activeFilter === 'Checked') return row.status === 'checked'
    return true
  }) ?? []

  const emptyCounts = { flagged: 0, new: 0, checked: 0, approved: 0, returned: 0, pending: 0 }

  function handleSaved(newRows: QueueRow[]) {
    void refetch()
    if (newRows.length > 0) setSelectedId(newRows[0].id)
  }

  const isAudit = hash === '#audit'
  const isImport = hash === '#import'
  const isHistory = hash === '#history'
  const isQuickCheck = hash === '#quick-check'

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <AppHeader
        onAddRequests={() => setDialogOpen(true)}
        addRequestsRef={addBtnRef}
        role={role}
        username={username}
        hash={hash}
      />
      {dialogOpen && (
        <AddRequestsDialog
          onClose={() => setDialogOpen(false)}
          onSaved={handleSaved}
        />
      )}

      {isImport && <ImportPage />}
      {isHistory && <HistoryPage />}
      {isQuickCheck && <QuickCheckPage />}
      {isAudit && <AuditLogPage />}

      {!isImport && !isHistory && !isQuickCheck && !isAudit && <main style={{
        width: '100%',
        maxWidth: 1240,
        margin: '0 auto',
        boxSizing: 'border-box',
        padding: '28px 28px 40px',
        display: 'flex',
        flexDirection: 'column',
        gap: 28,
      }}>
        {/* Error state */}
        {queueError && (
          <div style={{
            padding: '12px 16px',
            border: '1px solid #FDEBDD',
            borderRadius: 8,
            color: '#9A3412',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}>
            <span>Failed to load requests.</span>
            <button
              type="button"
              onClick={() => { void refetch() }}
              style={{
                height: 32,
                padding: '0 12px',
                border: '1px solid #9A3412',
                borderRadius: 6,
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
        )}

        {/* Loading state */}
        {queueLoading && (
          <>
            <QueueHeader
              rows={[]}
              counts={emptyCounts}
              activeFilter={activeFilter}
              onFilterChange={setActiveFilter}
            />
            <div style={{ border: '1px solid #E6E6E2', borderRadius: 12, overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 980 }}>
                <thead>
                  <tr style={{ background: '#F7F7F5', textAlign: 'left', fontSize: 12, color: '#5E5E59' }}>
                    {['#', 'Item', 'Dept.', 'Qty', 'Quoted / unit', 'Reference / unit', 'Diff.', 'Checked via', 'Status'].map((col) => (
                      <th key={col} style={{ padding: '11px 16px', fontWeight: 500 }}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <SkeletonRows count={4} />
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Empty state */}
        {!queueLoading && !queueError && queueData?.rows.length === 0 && (
          <div style={{ textAlign: 'center', padding: '80px 0', color: '#6B6B66', fontSize: 15 }}>
            <p style={{ margin: '0 0 16px' }}>No requests yet today.</p>
            {canAddRequests(role) && <button
              type="button"
              onClick={() => setDialogOpen(true)}
              style={{
                height: 44,
                padding: '0 20px',
                border: 0,
                borderRadius: 10,
                background: '#1A1A1A',
                color: '#FFFFFF',
                font: 'inherit',
                fontSize: 14,
                cursor: 'pointer',
              }}
            >
              Add requests
            </button>}
          </div>
        )}

        {/* Normal state */}
        {!queueLoading && !queueError && queueData && queueData.rows.length > 0 && (
          <>
            <QueueHeader
              rows={queueData.rows}
              counts={queueData.counts}
              activeFilter={activeFilter}
              onFilterChange={setActiveFilter}
            />
            <QueueTable
              rows={filteredRows}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
            <Inspector detail={detail} isLoading={detailLoading} role={role} />
          </>
        )}
      </main>}
    </div>
  )
}

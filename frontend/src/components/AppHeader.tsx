import { useEffect, useState } from 'react'

interface AppHeaderProps {
  onAddRequests?: () => void
  addRequestsRef?: React.Ref<HTMLButtonElement>
  role?: string | null
  hash?: string
}

type AiStatus = 'ok' | 'down' | 'not configured'

function useAiStatus(): AiStatus {
  const [status, setStatus] = useState<AiStatus>('ok')

  useEffect(() => {
    let cancelled = false

    async function check() {
      try {
        const res = await fetch('/api/health')
        if (!res.ok) { if (!cancelled) setStatus('down'); return }
        const data = await res.json()
        if (!cancelled) {
          if (data.langflow === 'not configured') setStatus('not configured')
          else if (data.langflow !== 'ok') setStatus('down')
          else setStatus('ok')
        }
      } catch {
        if (!cancelled) setStatus('down')
      }
    }

    check()
    const id = setInterval(check, 30_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  return status
}

const NAV_TABS = ['Today', 'Quick check', 'History', 'Import', 'Audit Log'] as const
type NavTab = typeof NAV_TABS[number]

function tabToHash(tab: NavTab): string {
  if (tab === 'Quick check') return '#quick-check'
  if (tab === 'Audit Log') return '#audit'
  return '#' + tab.toLowerCase()
}

export default function AppHeader({ onAddRequests, addRequestsRef, role, hash }: AppHeaderProps) {
  const aiStatus = useAiStatus()

  function handleTabClick(tab: NavTab) {
    window.location.hash = tabToHash(tab)
  }

  function activeTab(): NavTab {
    const h = (hash || window.location.hash || '#today').toLowerCase()
    if (h === '#history') return 'History'
    if (h === '#import') return 'Import'
    if (h === '#quick-check') return 'Quick check'
    if (h === '#audit') return 'Audit Log'
    return 'Today'
  }

  const active = activeTab()
  const showAuditLog = role === 'owner' || role === 'finance'

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: 12,
      padding: '16px 28px',
      borderBottom: '1px solid #EDEDEA',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 600, fontSize: 16 }}>Procur.AI</span>
          {aiStatus !== 'ok' && (
            <span style={{
              fontSize: 11,
              fontWeight: 500,
              color: '#9A3412',
              background: '#FDEBDD',
              padding: '2px 7px',
              borderRadius: 5,
              letterSpacing: '0.01em',
            }}>
              {aiStatus === 'not configured' ? 'AI not configured' : 'AI offline'}
            </span>
          )}
        </div>
        <nav aria-label="Main" style={{ display: 'flex', gap: 4, fontSize: 14 }}>
          {NAV_TABS.filter((tab) => tab !== 'Audit Log' || showAuditLog).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => handleTabClick(tab)}
              style={{
                padding: '8px 12px',
                borderRadius: 8,
                border: 0,
                background: active === tab ? '#F2F2EF' : 'transparent',
                color: active === tab ? '#1A1A1A' : '#4A4A46',
                font: 'inherit',
                fontSize: 14,
                cursor: 'pointer',
              }}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        {role && (
          <span style={{ fontSize: 12, color: '#4A4A46' }}>
            Logged in as: <span style={{ fontWeight: 500, color: '#1A1A1A' }}>{role}</span>
          </span>
        )}
        <button
          type="button"
          onClick={() => {
            localStorage.removeItem('token')
            localStorage.removeItem('role')
            window.location.reload()
          }}
          style={{
            height: 40,
            padding: '0 12px',
            border: '1px solid #D9D9D5',
            borderRadius: 8,
            background: 'transparent',
            color: '#4A4A46',
            font: 'inherit',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          Logout
        </button>
        {role !== 'finance' && (
          <button
            ref={addRequestsRef}
            type="button"
            onClick={onAddRequests}
            style={{
              height: 40,
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
            Add requests
          </button>
        )}
      </div>
    </header>
  )
}
import { useEffect, useState } from 'react'

interface AppHeaderProps {
  onAddRequests?: () => void
  addRequestsRef?: React.Ref<HTMLButtonElement>
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

const NAV_TABS = ['Today', 'Quick check', 'History', 'Import'] as const
type NavTab = typeof NAV_TABS[number]

function tabToHash(tab: NavTab): string {
  if (tab === 'Quick check') return '#quick-check'
  return '#' + tab.toLowerCase()
}

export default function AppHeader({ onAddRequests, addRequestsRef }: AppHeaderProps) {
  const aiStatus = useAiStatus()

  // Derive active tab from current hash
  const [currentHash, setCurrentHash] = useState(() => window.location.hash || '#today')
  useEffect(() => {
    function onHashChange() { setCurrentHash(window.location.hash || '#today') }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  function handleTabClick(tab: NavTab) {
    window.location.hash = tabToHash(tab)
  }

  function activeTab(): NavTab {
    const h = currentHash.toLowerCase()
    if (h === '#history') return 'History'
    if (h === '#import') return 'Import'
    if (h === '#quick-check') return 'Quick check'
    return 'Today'
  }

  const active = activeTab()

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
          {NAV_TABS.map((tab) => (
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
    </header>
  )
}

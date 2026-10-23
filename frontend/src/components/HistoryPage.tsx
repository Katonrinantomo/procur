import { useState } from 'react'
import PurchasesTab from './PurchasesTab'
import RequestsTab from './RequestsTab'

type SubTab = 'Purchases' | 'Requests'

const chipActive: React.CSSProperties = {
  padding: '6px 14px',
  borderRadius: 999,
  border: 0,
  background: '#1A1A1A',
  color: '#FFFFFF',
  font: 'inherit',
  fontSize: 13,
  cursor: 'pointer',
}
const chipInactive: React.CSSProperties = {
  padding: '6px 14px',
  borderRadius: 999,
  border: '1px solid #E0E0DB',
  background: 'transparent',
  color: '#4A4A46',
  font: 'inherit',
  fontSize: 13,
  cursor: 'pointer',
}

export default function HistoryPage() {
  const [activeTab, setActiveTab] = useState<SubTab>('Purchases')

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
      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#1A1A1A' }}>History</h1>
        <div style={{ display: 'flex', gap: 6 }}>
          {(['Purchases', 'Requests'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              style={activeTab === tab ? chipActive : chipInactive}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {activeTab === 'Purchases' && <PurchasesTab />}
      {activeTab === 'Requests' && <RequestsTab />}
    </main>
  )
}

import { useState } from 'react'

interface ReturnDialogProps {
  itemName: string
  onConfirm: (note: string) => void
  onCancel: () => void
  isSending: boolean
}

export default function ReturnDialog({ itemName, onConfirm, onCancel, isSending }: ReturnDialogProps) {
  const [note, setNote] = useState('')
  const trimmed = note.trim()

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') onCancel()
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '0 16px',
      }}
      role="dialog"
      aria-modal
      aria-labelledby="return-dialog-title"
      onKeyDown={handleKeyDown}
    >
      {/* Backdrop */}
      <div
        style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.18)' }}
        onClick={onCancel}
        aria-hidden
      />

      {/* Dialog box */}
      <div style={{
        position: 'relative',
        zIndex: 1,
        width: '100%',
        maxWidth: 420,
        background: '#FFFFFF',
        border: '1px solid #E6E6E2',
        borderRadius: 12,
        padding: 24,
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <h2 id="return-dialog-title" style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
            Return to requester
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: '#6B6B66' }}>
            {itemName}
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label htmlFor="return-note" style={{ fontSize: 13, color: '#4A4A46' }}>
            Note <span style={{ color: '#9A3412' }}>*</span>
          </label>
          <textarea
            id="return-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Explain why this request is being returned…"
            rows={4}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '10px 12px',
              fontSize: 14,
              fontFamily: 'inherit',
              border: '1px solid #E0E0DB',
              borderRadius: 8,
              resize: 'vertical',
              outline: 'none',
              color: '#1A1A1A',
              background: '#FFFFFF',
            }}
            autoFocus
          />
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button
            type="button"
            onClick={onCancel}
            disabled={isSending}
            style={{
              height: 40,
              padding: '0 16px',
              border: '1px solid #E0E0DB',
              borderRadius: 10,
              background: '#FFFFFF',
              font: 'inherit',
              fontSize: 14,
              cursor: isSending ? 'not-allowed' : 'pointer',
              color: '#1A1A1A',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => { if (trimmed) onConfirm(trimmed) }}
            disabled={!trimmed || isSending}
            style={{
              height: 40,
              padding: '0 16px',
              border: 0,
              borderRadius: 10,
              background: !trimmed || isSending ? '#9E9E99' : '#1A1A1A',
              color: '#FFFFFF',
              font: 'inherit',
              fontSize: 14,
              cursor: !trimmed || isSending ? 'not-allowed' : 'pointer',
            }}
          >
            {isSending ? 'Sending…' : 'Return'}
          </button>
        </div>
      </div>
    </div>
  )
}

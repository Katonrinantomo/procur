import { useState } from 'react'
import type { OutcomeTag } from '../types/api'

export type DecisionMode = 'return' | 'override'

interface DecisionDialogProps {
  mode: DecisionMode
  itemName: string
  onConfirm: (reason: string, outcomeTag: OutcomeTag | null) => void
  onCancel: () => void
  isSending: boolean
  error?: string | null
}

const COPY: Record<DecisionMode, { title: string; placeholder: string; confirm: string; sending: string }> = {
  return: {
    title: 'Return to requester',
    placeholder: 'Explain why this request is being returned…',
    confirm: 'Return',
    sending: 'Sending…',
  },
  override: {
    title: 'Approve despite flags',
    placeholder: 'Explain why this row is safe to approve…',
    confirm: 'Approve',
    sending: 'Approving…',
  },
}

const OUTCOME_OPTIONS: { value: OutcomeTag; label: string; hint: string }[] = [
  { value: 'false_alarm', label: 'False alarm', hint: 'The flag was wrong' },
  { value: 'risk_accepted', label: 'Risk accepted', hint: 'The flag is right; approving anyway' },
]

export default function DecisionDialog({ mode, itemName, onConfirm, onCancel, isSending, error }: DecisionDialogProps) {
  const [reason, setReason] = useState('')
  const [outcomeTag, setOutcomeTag] = useState<OutcomeTag | null>(null)
  const trimmed = reason.trim()
  const copy = COPY[mode]
  const ready = trimmed !== '' && (mode === 'return' || outcomeTag !== null) && !isSending

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
      aria-labelledby="decision-dialog-title"
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
          <h2 id="decision-dialog-title" style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
            {copy.title}
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: '#6B6B66' }}>
            {itemName}
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label htmlFor="decision-reason" style={{ fontSize: 13, color: '#4A4A46' }}>
            Reason <span style={{ color: '#9A3412' }}>*</span>
          </label>
          <textarea
            id="decision-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={copy.placeholder}
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

        {mode === 'override' && (
          <fieldset style={{ margin: 0, padding: 0, border: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <legend style={{ padding: 0, marginBottom: 6, fontSize: 13, color: '#4A4A46' }}>
              Outcome <span style={{ color: '#9A3412' }}>*</span>
            </legend>
            {OUTCOME_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  padding: '10px 12px',
                  border: `1px solid ${outcomeTag === opt.value ? '#1A1A1A' : '#E0E0DB'}`,
                  borderRadius: 8,
                  cursor: 'pointer',
                }}
              >
                <input
                  type="radio"
                  name="outcome-tag"
                  value={opt.value}
                  checked={outcomeTag === opt.value}
                  onChange={() => setOutcomeTag(opt.value)}
                  style={{ margin: '2px 0 0' }}
                />
                <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontSize: 14, color: '#1A1A1A' }}>{opt.label}</span>
                  <span style={{ fontSize: 12, color: '#6B6B66' }}>{opt.hint}</span>
                </span>
              </label>
            ))}
          </fieldset>
        )}

        {error && (
          <p style={{ margin: 0, fontSize: 13, color: '#9A3412' }}>{error}</p>
        )}

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
            onClick={() => { if (ready) onConfirm(trimmed, mode === 'override' ? outcomeTag : null) }}
            disabled={!ready}
            style={{
              height: 40,
              padding: '0 16px',
              border: 0,
              borderRadius: 10,
              background: ready ? '#1A1A1A' : '#9E9E99',
              color: '#FFFFFF',
              font: 'inherit',
              fontSize: 14,
              cursor: ready ? 'pointer' : 'not-allowed',
            }}
          >
            {isSending ? copy.sending : copy.confirm}
          </button>
        </div>
      </div>
    </div>
  )
}

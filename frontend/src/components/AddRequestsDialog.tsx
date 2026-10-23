/**
 * AddRequestsDialog — two-step modal for submitting procurement requests.
 *
 * Step 1: Paste raw text + "Requested by", call POST /api/requests/parse
 * Step 2: Editable preview table, then POST /api/requests to save
 */
import { useEffect, useRef, useState, useId } from 'react'
import type { LineItemDraft, QueueRow } from '../types/api'

// ─── shared token values (match design/reference.html) ───────────────────────
const S = {
  border: '1px solid #E6E6E2',
  borderLight: '1px solid #EDEDEA',
  radius: 10,
  radiusSm: 8,
  bg: '#FFFFFF',
  surface: '#F7F7F5',
  text: '#1A1A1A',
  muted: '#6B6B66',
  subtle: '#4A4A46',
  label: '#5E5E59',
  btnPrimary: { background: '#1A1A1A', color: '#FFFFFF', border: 0 } as React.CSSProperties,
  btnSecondary: { background: '#FFFFFF', color: '#1A1A1A', border: '1px solid #E0E0DB' } as React.CSSProperties,
  inputBase: {
    height: 36,
    padding: '0 10px',
    border: '1px solid #E0E0DB',
    borderRadius: 8,
    font: 'inherit',
    fontSize: 13,
    color: '#1A1A1A',
    background: '#FFFFFF',
    boxSizing: 'border-box',
    width: '100%',
    outline: 'none',
  } as React.CSSProperties,
}

// ─── types ────────────────────────────────────────────────────────────────────

interface DraftRow extends LineItemDraft {
  _key: string   // stable local key for list rendering
}

interface AddRequestsDialogProps {
  onClose: () => void
  onSaved: (newRows: QueueRow[]) => void
}

// ─── helpers ──────────────────────────────────────────────────────────────────

function makeDraftRow(partial: Partial<LineItemDraft> = {}): DraftRow {
  return {
    _key: Math.random().toString(36).slice(2),
    name: partial.name ?? '',
    qty: partial.qty ?? null,
    unit: partial.unit ?? null,
    department: partial.department ?? null,
    quoted_unit_price_idr: partial.quoted_unit_price_idr ?? null,
    supplier: partial.supplier ?? null,
  }
}

// ─── sub-components ───────────────────────────────────────────────────────────

function FieldLabel({ htmlFor, children }: { htmlFor: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} style={{ fontSize: 12, color: S.label, fontWeight: 500, display: 'block', marginBottom: 5 }}>
      {children}
    </label>
  )
}

interface CellInputProps {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  required?: boolean
  invalid?: boolean
  width?: number | string
  numeric?: boolean
  ariaLabel: string
}

function CellInput({ value, onChange, placeholder, required, invalid, width, numeric, ariaLabel }: CellInputProps) {
  return (
    <input
      type={numeric ? 'number' : 'text'}
      aria-label={ariaLabel}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      required={required}
      style={{
        ...S.inputBase,
        width: width ?? '100%',
        borderColor: invalid ? '#9A3412' : '#E0E0DB',
        fontFamily: numeric ? "'Geist Mono', monospace" : 'inherit',
        fontVariantNumeric: numeric ? 'tabular-nums' : undefined,
        minWidth: 0,
      }}
    />
  )
}

// ─── main component ───────────────────────────────────────────────────────────

export default function AddRequestsDialog({ onClose, onSaved }: AddRequestsDialogProps) {
  // Step 1 state
  const [step, setStep] = useState<1 | 2>(1)
  const [pastedText, setPastedText] = useState('')
  const [requestedBy, setRequestedBy] = useState('')
  const [organizing, setOrganizing] = useState(false)
  const [parseError, setParseError] = useState<string | null>(null)

  // Step 2 state
  const [rows, setRows] = useState<DraftRow[]>([])
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [submitAttempted, setSubmitAttempted] = useState(false)

  // Focus management
  const addBtnTriggerRef = useRef<HTMLButtonElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const backdropRef = useRef<HTMLDivElement | null>(null)
  const pasteId = useId()
  const requestedById = useId()

  // Store the opener button so we can return focus to it on close
  useEffect(() => {
    addBtnTriggerRef.current = document.activeElement as HTMLButtonElement | null
    // Autofocus textarea on mount
    setTimeout(() => textareaRef.current?.focus(), 0)
  }, [])

  // Trap Esc
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') handleClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  })

  function handleClose() {
    onClose()
    setTimeout(() => addBtnTriggerRef.current?.focus(), 0)
  }

  // ── Step 1: parse ──────────────────────────────────────────────────────────

  async function handleOrganize() {
    if (!pastedText.trim()) return
    setOrganizing(true)
    setParseError(null)
    try {
      const res = await fetch('/api/requests/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: pastedText, requested_by: requestedBy || undefined }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string }
        throw new Error(body.detail ?? `Server error ${res.status}`)
      }
      const drafts = await res.json() as LineItemDraft[]
      setRows(drafts.map((d) => makeDraftRow(d)))
      setStep(2)
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setOrganizing(false)
    }
  }

  // ── Step 2: row editing ────────────────────────────────────────────────────

  function updateRow(key: string, field: keyof LineItemDraft, value: string) {
    setRows((prev) =>
      prev.map((r) => {
        if (r._key !== key) return r
        if (field === 'qty' || field === 'quoted_unit_price_idr') {
          const n = value === '' ? null : parseInt(value, 10)
          return { ...r, [field]: Number.isNaN(n) ? null : n }
        }
        return { ...r, [field]: value === '' ? null : value }
      }),
    )
  }

  function deleteRow(key: string) {
    setRows((prev) => prev.filter((r) => r._key !== key))
  }

  function addRow() {
    setRows((prev) => [...prev, makeDraftRow()])
  }

  // ── Step 2: save ───────────────────────────────────────────────────────────

  async function handleSave() {
    setSubmitAttempted(true)
    const invalid = rows.some((r) => !r.name.trim() || r.qty === null || r.qty === undefined)
    if (invalid || rows.length === 0) return

    setSaving(true)
    setSaveError(null)
    try {
      const items = rows.map((r, i) => ({
        line_no: i + 1,
        raw_name: r.name,
        department: r.department || undefined,
        qty: r.qty,
        unit: r.unit || undefined,
        quoted_unit_price_idr: r.quoted_unit_price_idr || undefined,
        quoting_supplier_name: r.supplier || undefined,
      }))
      const res = await fetch('/api/requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requested_by: requestedBy || undefined,
          raw_text: pastedText || undefined,
          items,
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string }
        throw new Error(body.detail ?? `Server error ${res.status}`)
      }
      const newRows = await res.json() as QueueRow[]
      onSaved(newRows)
      handleClose()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  // ─── Backdrop click ────────────────────────────────────────────────────────
  function onBackdropClick(e: React.MouseEvent) {
    if (e.target === backdropRef.current) handleClose()
  }

  // ─── Render ────────────────────────────────────────────────────────────────
  return (
    <div
      ref={backdropRef}
      onClick={onBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label="Add requests"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.35)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: 60,
        paddingBottom: 40,
        zIndex: 1000,
        overflowY: 'auto',
      }}
    >
      <div
        style={{
          background: S.bg,
          border: S.border,
          borderRadius: 14,
          width: '100%',
          maxWidth: step === 1 ? 520 : 860,
          boxSizing: 'border-box',
          padding: 28,
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
          margin: '0 16px',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600, color: S.text }}>
            {step === 1 ? 'Add requests' : 'Review & confirm'}
          </h2>
          <button
            type="button"
            aria-label="Close dialog"
            onClick={handleClose}
            style={{
              width: 32,
              height: 32,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: S.borderLight,
              borderRadius: S.radiusSm,
              background: S.bg,
              cursor: 'pointer',
              fontSize: 18,
              color: S.subtle,
              lineHeight: 1,
              padding: 0,
            }}
          >
            ×
          </button>
        </div>

        {/* ── STEP 1 ── */}
        {step === 1 && (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <FieldLabel htmlFor={pasteId}>Paste requests</FieldLabel>
                <textarea
                  id={pasteId}
                  ref={textareaRef}
                  value={pastedText}
                  onChange={(e) => setPastedText(e.target.value)}
                  placeholder="Paste your purchase request list here…"
                  rows={8}
                  style={{
                    width: '100%',
                    boxSizing: 'border-box',
                    padding: '10px 12px',
                    border: '1px solid #E0E0DB',
                    borderRadius: S.radiusSm,
                    font: 'inherit',
                    fontSize: 14,
                    color: S.text,
                    background: S.bg,
                    resize: 'vertical',
                    outline: 'none',
                    lineHeight: 1.6,
                  }}
                />
              </div>
              <div>
                <FieldLabel htmlFor={requestedById}>Requested by</FieldLabel>
                <input
                  id={requestedById}
                  type="text"
                  value={requestedBy}
                  onChange={(e) => setRequestedBy(e.target.value)}
                  placeholder="Department or person name"
                  style={{ ...S.inputBase, height: 40, fontSize: 14 }}
                />
              </div>
            </div>

            {/* Parse error */}
            {parseError && (
              <div style={{
                padding: '10px 14px',
                border: '1px solid #FDEBDD',
                borderRadius: S.radiusSm,
                color: '#9A3412',
                fontSize: 13,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}>
                <span style={{ flex: 1 }}>{parseError}</span>
                <button
                  type="button"
                  onClick={() => { void handleOrganize() }}
                  style={{
                    height: 30,
                    padding: '0 10px',
                    border: '1px solid #9A3412',
                    borderRadius: 6,
                    background: 'transparent',
                    color: '#9A3412',
                    font: 'inherit',
                    fontSize: 12,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    flexShrink: 0,
                  }}
                >
                  Retry
                </button>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => { void handleOrganize() }}
                disabled={organizing || !pastedText.trim()}
                style={{
                  ...S.btnPrimary,
                  height: 40,
                  padding: '0 20px',
                  borderRadius: S.radius,
                  font: 'inherit',
                  fontSize: 14,
                  cursor: organizing || !pastedText.trim() ? 'not-allowed' : 'pointer',
                  opacity: organizing || !pastedText.trim() ? 0.6 : 1,
                }}
              >
                {organizing ? 'Organizing…' : 'Organize'}
              </button>
            </div>
          </>
        )}

        {/* ── STEP 2 ── */}
        {step === 2 && (
          <>
            {/* Step 2: back link */}
            <div style={{ marginTop: -8 }}>
              <button
                type="button"
                onClick={() => { setStep(1); setSaveError(null); setSubmitAttempted(false) }}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  font: 'inherit',
                  fontSize: 13,
                  color: S.subtle,
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  textUnderlineOffset: 2,
                }}
              >
                ← Edit pasted text
              </button>
            </div>

            {/* Editable table */}
            <div style={{ border: S.border, borderRadius: 10, overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 700 }}>
                <thead>
                  <tr style={{ background: S.surface, textAlign: 'left', fontSize: 12, color: S.label }}>
                    {['Item', 'Qty *', 'Unit', 'Dept.', 'Quoted / unit', 'Supplier', ''].map((col) => (
                      <th key={col} style={{ padding: '10px 10px', fontWeight: 500, whiteSpace: 'nowrap' }}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ padding: '20px 16px', textAlign: 'center', color: S.muted, fontSize: 13 }}>
                        No rows yet. Click "Add row" to add one.
                      </td>
                    </tr>
                  )}
                  {rows.map((row) => {
                    const qtyInvalid = submitAttempted && (row.qty === null || row.qty === undefined)
                    const nameInvalid = submitAttempted && !row.name.trim()
                    return (
                      <tr key={row._key} style={{ borderTop: S.borderLight }}>
                        <td style={{ padding: '8px 8px 8px 10px', minWidth: 160 }}>
                          <CellInput
                            ariaLabel="Item name"
                            value={row.name}
                            onChange={(v) => updateRow(row._key, 'name', v)}
                            placeholder="Item name"
                            required
                            invalid={nameInvalid}
                          />
                        </td>
                        <td style={{ padding: '8px 8px', width: 80 }}>
                          <CellInput
                            ariaLabel="Quantity"
                            value={row.qty !== null && row.qty !== undefined ? String(row.qty) : ''}
                            onChange={(v) => updateRow(row._key, 'qty', v)}
                            placeholder="0"
                            required
                            invalid={qtyInvalid}
                            numeric
                          />
                        </td>
                        <td style={{ padding: '8px 8px', width: 80 }}>
                          <CellInput
                            ariaLabel="Unit"
                            value={row.unit ?? ''}
                            onChange={(v) => updateRow(row._key, 'unit', v)}
                            placeholder="pcs"
                          />
                        </td>
                        <td style={{ padding: '8px 8px', width: 110 }}>
                          <CellInput
                            ariaLabel="Department"
                            value={row.department ?? ''}
                            onChange={(v) => updateRow(row._key, 'department', v)}
                            placeholder="Dept."
                          />
                        </td>
                        <td style={{ padding: '8px 8px', width: 130 }}>
                          <CellInput
                            ariaLabel="Quoted price per unit"
                            value={row.quoted_unit_price_idr !== null && row.quoted_unit_price_idr !== undefined
                              ? String(row.quoted_unit_price_idr)
                              : ''}
                            onChange={(v) => updateRow(row._key, 'quoted_unit_price_idr', v)}
                            placeholder="0"
                            numeric
                          />
                        </td>
                        <td style={{ padding: '8px 8px', minWidth: 140 }}>
                          <CellInput
                            ariaLabel="Supplier"
                            value={row.supplier ?? ''}
                            onChange={(v) => updateRow(row._key, 'supplier', v)}
                            placeholder="Supplier name"
                          />
                        </td>
                        <td style={{ padding: '8px 8px 8px 4px', width: 36, textAlign: 'center' }}>
                          <button
                            type="button"
                            aria-label="Delete row"
                            onClick={() => deleteRow(row._key)}
                            style={{
                              width: 28,
                              height: 28,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              border: '1px solid #E0E0DB',
                              borderRadius: 6,
                              background: S.bg,
                              cursor: 'pointer',
                              color: S.subtle,
                              fontSize: 15,
                              padding: 0,
                              lineHeight: 1,
                            }}
                          >
                            ×
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Add row */}
            <div>
              <button
                type="button"
                onClick={addRow}
                style={{
                  ...S.btnSecondary,
                  height: 34,
                  padding: '0 14px',
                  borderRadius: S.radiusSm,
                  font: 'inherit',
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                + Add row
              </button>
            </div>

            {/* Validation hint */}
            {submitAttempted && rows.some((r) => !r.name.trim() || r.qty === null) && (
              <p style={{ margin: 0, fontSize: 12, color: '#9A3412' }}>
                Qty is required for all rows, and Item name must not be blank.
              </p>
            )}

            {/* Save error */}
            {saveError && (
              <div style={{
                padding: '10px 14px',
                border: '1px solid #FDEBDD',
                borderRadius: S.radiusSm,
                color: '#9A3412',
                fontSize: 13,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}>
                <span style={{ flex: 1 }}>{saveError}</span>
                <button
                  type="button"
                  onClick={() => { void handleSave() }}
                  style={{
                    height: 30,
                    padding: '0 10px',
                    border: '1px solid #9A3412',
                    borderRadius: 6,
                    background: 'transparent',
                    color: '#9A3412',
                    font: 'inherit',
                    fontSize: 12,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    flexShrink: 0,
                  }}
                >
                  Retry
                </button>
              </div>
            )}

            {/* Footer actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                type="button"
                onClick={handleClose}
                style={{
                  ...S.btnSecondary,
                  height: 40,
                  padding: '0 16px',
                  borderRadius: S.radius,
                  font: 'inherit',
                  fontSize: 14,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => { void handleSave() }}
                disabled={saving || rows.length === 0}
                style={{
                  ...S.btnPrimary,
                  height: 40,
                  padding: '0 20px',
                  borderRadius: S.radius,
                  font: 'inherit',
                  fontSize: 14,
                  cursor: saving || rows.length === 0 ? 'not-allowed' : 'pointer',
                  opacity: saving || rows.length === 0 ? 0.6 : 1,
                }}
              >
                {saving ? 'Saving…' : 'Save and check'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

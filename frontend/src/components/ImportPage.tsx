import { useState, useRef } from 'react'

interface ImportError {
  line: number
  message: string
}

interface ImportSummary {
  inserted: number
  skipped: number
  new_items: number
  new_suppliers: number
  errors: ImportError[]
}

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null)
  const [summary, setSummary] = useState<ImportSummary | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null
    setFile(f)
    setSummary(null)
    setUploadError(null)
  }

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setSummary(null)
    setUploadError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const resp = await fetch('/api/imports/purchases', { method: 'POST', body: form })
      if (!resp.ok) {
        const text = await resp.text()
        setUploadError(`Server error ${resp.status}: ${text}`)
        return
      }
      const data: ImportSummary = await resp.json()
      setSummary(data)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setUploading(false)
    }
  }

  const statCellStyle: React.CSSProperties = {
    padding: '13px 16px',
    fontFamily: "'Geist Mono', monospace",
    fontVariantNumeric: 'tabular-nums',
    textAlign: 'right',
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
      gap: 28,
    }}>
      {/* Page heading */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Import Purchases</h1>
        <span style={{ fontSize: 13, color: '#6B6B66' }}>
          Upload an Excel file (.xlsx) with columns: date, po_number, supplier, item, qty, unit, unit_price_idr
        </span>
      </div>

      {/* Upload card */}
      <div style={{
        border: '1px solid #E6E6E2',
        borderRadius: 12,
        padding: '24px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        maxWidth: 560,
      }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: '#1A1A1A' }}>Excel file (.xlsx)</span>
            <a
              href="/api/imports/purchases/template"
              download="procur-purchases-template.xlsx"
              style={{ fontSize: 12, color: '#3b82d4', textDecoration: 'none' }}
            >
              Download template
            </a>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              style={{
                height: 36,
                padding: '0 14px',
                border: '1px solid #D1D1CB',
                borderRadius: 8,
                background: '#FFFFFF',
                color: '#1A1A1A',
                font: 'inherit',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              Choose file
            </button>
            <span style={{ fontSize: 13, color: file ? '#1A1A1A' : '#6B6B66' }}>
              {file ? file.name : 'No file chosen'}
            </span>
          </div>
        </label>

        <button
          type="button"
          disabled={!file || uploading}
          onClick={() => void handleUpload()}
          style={{
            alignSelf: 'flex-start',
            height: 40,
            padding: '0 20px',
            border: 0,
            borderRadius: 10,
            background: file && !uploading ? '#1A1A1A' : '#B0B0AB',
            color: '#FFFFFF',
            font: 'inherit',
            fontSize: 14,
            cursor: file && !uploading ? 'pointer' : 'not-allowed',
          }}
        >
          {uploading ? 'Uploading…' : 'Upload'}
        </button>

        {uploadError && (
          <div style={{
            padding: '10px 14px',
            border: '1px solid #FDEBDD',
            borderRadius: 8,
            color: '#9A3412',
            fontSize: 13,
          }}>
            {uploadError}
          </div>
        )}
      </div>

      {/* Summary table */}
      {summary && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Import summary</h2>

          <div style={{ border: '1px solid #E6E6E2', borderRadius: 12, overflow: 'hidden', maxWidth: 480 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr style={{ background: '#F7F7F5', textAlign: 'left', fontSize: 12, color: '#5E5E59' }}>
                  <th style={{ padding: '11px 16px', fontWeight: 500 }}>Result</th>
                  <th style={{ padding: '11px 16px', fontWeight: 500, textAlign: 'right' }}>Count</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { label: 'Rows inserted', value: summary.inserted, highlight: summary.inserted > 0 },
                  { label: 'Rows skipped (duplicate)', value: summary.skipped, highlight: false },
                  { label: 'New catalog items created', value: summary.new_items, highlight: false },
                  { label: 'New suppliers created', value: summary.new_suppliers, highlight: false },
                ].map(({ label, value, highlight }) => (
                  <tr key={label} style={{ borderTop: '1px solid #EDEDEA' }}>
                    <td style={{ padding: '13px 16px', color: '#1A1A1A' }}>{label}</td>
                    <td style={{
                      ...statCellStyle,
                      fontWeight: highlight ? 600 : 400,
                      color: highlight ? '#1A1A1A' : '#4A4A46',
                    }}>
                      {value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Errors table */}
          {summary.errors.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: '#9A3412' }}>
                {summary.errors.length} row{summary.errors.length !== 1 ? 's' : ''} had errors
              </span>
              <div style={{ border: '1px solid #FDEBDD', borderRadius: 12, overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: '#FFF8F2', textAlign: 'left', color: '#9A3412' }}>
                      <th style={{ padding: '10px 16px', fontWeight: 500 }}>Line</th>
                      <th style={{ padding: '10px 16px', fontWeight: 500 }}>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.errors.map((err) => (
                      <tr key={err.line} style={{ borderTop: '1px solid #FDEBDD' }}>
                        <td style={{
                          padding: '11px 16px',
                          fontFamily: "'Geist Mono', monospace",
                          fontVariantNumeric: 'tabular-nums',
                          color: '#9A3412',
                          whiteSpace: 'nowrap',
                        }}>
                          {err.line}
                        </td>
                        <td style={{ padding: '11px 16px', color: '#1A1A1A' }}>{err.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  )
}

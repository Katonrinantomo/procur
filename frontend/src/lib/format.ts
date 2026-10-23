/**
 * Formatting utilities for Procur.AI.
 * All monetary values are integer rupiah — never pass a float.
 */

/** "1.450.000" — no prefix */
export function formatRupiah(n: number): string {
  return new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(n)
}

/** "Rp 1.450.000" */
export function formatRupiahWithPrefix(n: number): string {
  return 'Rp ' + formatRupiah(n)
}

/**
 * "+29.5%" or "−2.0%"
 * Uses Unicode minus U+2212 for negatives.
 */
export function formatPct(n: number): string {
  const sign = n >= 0 ? '+' : '\u2212'
  return sign + Math.abs(n).toFixed(1) + '%'
}

/** "12 Aug 2026" */
export function formatDate(d: string | Date): string {
  const date = typeof d === 'string' ? new Date(d) : d
  return date.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

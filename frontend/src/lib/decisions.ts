/** Labels and the snapshot summary for decision-log rows (M19). */
import { formatRupiahWithPrefix } from './format'
import type { DecisionRow, OutcomeTag } from '../types/api'

export const DECISION_LABEL: Record<string, string> = {
  approve: 'Approved',
  return: 'Returned',
  pay: 'Paid',
  hold: 'Held',
  clarify: 'Clarification asked',
}

export const OUTCOME_LABEL: Record<OutcomeTag, string> = {
  false_alarm: 'False alarm',
  risk_accepted: 'Risk accepted',
}

const SOURCE_LABEL: Record<string, string> = {
  history: 'history',
  web: 'web',
  none: 'no reference',
}

/** One line describing what the decider saw, from the backend's snapshot. */
export function snapshotLine(d: DecisionRow): string | null {
  const s = d.snapshot
  if (!s) return null
  const parts: string[] = []
  if (s.risk_score != null) parts.push(`risk ${s.risk_score}/100`)
  const nFlags = s.flags?.length ?? 0
  parts.push(nFlags === 0 ? 'no flags' : `${nFlags} ${nFlags === 1 ? 'flag' : 'flags'} (${s.flags!.map((f) => f.code).join(', ')})`)
  if (s.reference_unit_price_idr != null) {
    const src = s.reference_source ? SOURCE_LABEL[s.reference_source] ?? s.reference_source : null
    parts.push(`ref ${formatRupiahWithPrefix(s.reference_unit_price_idr)}${src ? ` (${src})` : ''}`)
  }
  return `At decision: ${parts.join(' · ')}`
}

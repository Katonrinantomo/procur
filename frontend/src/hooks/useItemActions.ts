import { useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchWithAuth } from '../lib/api'
import type { OutcomeTag, RequestItemDetail } from '../types/api'

export interface ApproveInput {
  reason?: string
  outcome_tag?: OutcomeTag
}

async function errorFrom(res: Response, fallback: string): Promise<Error> {
  const data = await res.json().catch(() => ({})) as { detail?: unknown }
  return new Error(typeof data.detail === 'string' ? data.detail : `${fallback}: ${res.status}`)
}

async function postApprove(itemId: number, input: ApproveInput): Promise<RequestItemDetail> {
  const res = await fetchWithAuth(`/api/request-items/${itemId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!res.ok) throw await errorFrom(res, 'Approve failed')
  return res.json() as Promise<RequestItemDetail>
}

async function postReturn(itemId: number, reason: string): Promise<RequestItemDetail> {
  const res = await fetchWithAuth(`/api/request-items/${itemId}/return`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  })
  if (!res.ok) throw await errorFrom(res, 'Return failed')
  return res.json() as Promise<RequestItemDetail>
}

export function useApprove(itemId: number) {
  const qc = useQueryClient()
  return useMutation<RequestItemDetail, Error, ApproveInput>({
    mutationFn: (input: ApproveInput) => postApprove(itemId, input),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['request-item', itemId] })
      void qc.invalidateQueries({ queryKey: ['queue'] })
      void qc.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useReturn(itemId: number) {
  const qc = useQueryClient()
  return useMutation<RequestItemDetail, Error, string>({
    mutationFn: (reason: string) => postReturn(itemId, reason),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['request-item', itemId] })
      void qc.invalidateQueries({ queryKey: ['queue'] })
      void qc.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

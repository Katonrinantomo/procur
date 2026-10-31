import { useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchWithAuth } from '../lib/api'
import type { RequestItemDetail } from '../types/api'

async function errorFrom(res: Response, fallback: string): Promise<Error> {
  const data = await res.json().catch(() => ({})) as { detail?: unknown }
  return new Error(typeof data.detail === 'string' ? data.detail : `${fallback}: ${res.status}`)
}

async function postApprove(itemId: number): Promise<RequestItemDetail> {
  const res = await fetchWithAuth(`/api/request-items/${itemId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  if (!res.ok) throw await errorFrom(res, 'Approve failed')
  return res.json() as Promise<RequestItemDetail>
}

async function postReturn(itemId: number, note: string): Promise<RequestItemDetail> {
  const res = await fetchWithAuth(`/api/request-items/${itemId}/return`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note }),
  })
  if (!res.ok) throw await errorFrom(res, 'Return failed')
  return res.json() as Promise<RequestItemDetail>
}

export function useApprove(itemId: number) {
  const qc = useQueryClient()
  return useMutation<RequestItemDetail, Error, void>({
    mutationFn: () => postApprove(itemId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['request-item', itemId] })
      void qc.invalidateQueries({ queryKey: ['queue'] })
    },
  })
}

export function useReturn(itemId: number) {
  const qc = useQueryClient()
  return useMutation<RequestItemDetail, Error, string>({
    mutationFn: (note: string) => postReturn(itemId, note),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['request-item', itemId] })
      void qc.invalidateQueries({ queryKey: ['queue'] })
    },
  })
}

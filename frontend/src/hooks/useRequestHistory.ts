import { useQuery } from '@tanstack/react-query'
import type { RequestItemsListResponse } from '../types/api'

interface RequestHistoryParams {
  dateFrom: string
  dateTo: string
  status: string  // '' or 'all' = all statuses
  page: number
}

async function fetchRequestHistory(params: RequestHistoryParams): Promise<RequestItemsListResponse> {
  const qs = new URLSearchParams()
  if (params.dateFrom) qs.set('date_from', params.dateFrom)
  if (params.dateTo) qs.set('date_to', params.dateTo)
  if (params.status && params.status !== 'all') qs.set('status', params.status)
  qs.set('page', String(params.page))

  const res = await fetch(`/api/request-items?${qs.toString()}`)
  if (!res.ok) throw new Error(`Request history fetch failed: ${res.status}`)
  return res.json() as Promise<RequestItemsListResponse>
}

export function useRequestHistory(params: RequestHistoryParams) {
  return useQuery<RequestItemsListResponse, Error>({
    queryKey: ['request-history', params],
    queryFn: () => fetchRequestHistory(params),
    staleTime: 30_000,
  })
}

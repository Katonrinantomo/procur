import { useQuery } from '@tanstack/react-query'
import type { RequestItemDetail } from '../types/api'

async function fetchRequestItem(id: number): Promise<RequestItemDetail> {
  const res = await fetch(`/api/request-items/${id}`)
  if (!res.ok) throw new Error(`Item fetch failed: ${res.status}`)
  return res.json() as Promise<RequestItemDetail>
}

export function useRequestItem(id: number | null) {
  return useQuery<RequestItemDetail, Error>({
    queryKey: ['request-item', id],
    queryFn: () => fetchRequestItem(id!),
    enabled: id != null,
    staleTime: 30_000,
  })
}

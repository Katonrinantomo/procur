import { useQuery } from '@tanstack/react-query'
import type { QueueResponse } from '../types/api'

async function fetchQueue(): Promise<QueueResponse> {
  const res = await fetch('/api/queue')
  if (!res.ok) throw new Error(`Queue fetch failed: ${res.status}`)
  return res.json() as Promise<QueueResponse>
}

export function useQueue() {
  return useQuery<QueueResponse, Error>({
    queryKey: ['queue'],
    queryFn: fetchQueue,
    staleTime: 30_000,
  })
}

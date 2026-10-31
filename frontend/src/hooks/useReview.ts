import { useQuery } from '@tanstack/react-query'
import type { ReviewResponse } from '../types/api'
import { fetchWithAuth } from '../lib/api'

async function fetchReview(): Promise<ReviewResponse> {
  const res = await fetchWithAuth('/api/review')
  if (!res.ok) throw new Error(`Review fetch failed: ${res.status}`)
  return res.json() as Promise<ReviewResponse>
}

/** Undecided rows across dates, flagged first then by risk (sorted by the backend). */
export function useReview() {
  return useQuery<ReviewResponse, Error>({
    queryKey: ['review'],
    queryFn: fetchReview,
    staleTime: 30_000,
  })
}

import { useQuery } from '@tanstack/react-query'
import type { PurchasesResponse } from '../types/api'

interface PurchasesParams {
  search: string
  supplierId: string
  dateFrom: string
  dateTo: string
  page: number
}

async function fetchPurchases(params: PurchasesParams): Promise<PurchasesResponse> {
  const qs = new URLSearchParams()
  if (params.search) qs.set('search', params.search)
  if (params.supplierId) qs.set('supplier_id', params.supplierId)
  if (params.dateFrom) qs.set('date_from', params.dateFrom)
  if (params.dateTo) qs.set('date_to', params.dateTo)
  qs.set('page', String(params.page))

  const res = await fetch(`/api/purchases?${qs.toString()}`)
  if (!res.ok) throw new Error(`Purchases fetch failed: ${res.status}`)
  return res.json() as Promise<PurchasesResponse>
}

export function usePurchases(params: PurchasesParams) {
  return useQuery<PurchasesResponse, Error>({
    queryKey: ['purchases', params],
    queryFn: () => fetchPurchases(params),
    staleTime: 30_000,
  })
}

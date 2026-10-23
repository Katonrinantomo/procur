import { useQuery } from '@tanstack/react-query'
import type { SuppliersResponse } from '../types/api'

async function fetchItemSuppliers(itemId: number): Promise<SuppliersResponse> {
  const res = await fetch(`/api/items/${itemId}/suppliers`)
  if (!res.ok) throw new Error(`Suppliers fetch failed: ${res.status}`)
  return res.json() as Promise<SuppliersResponse>
}

export function useItemSuppliers(itemId: number | null) {
  return useQuery<SuppliersResponse, Error>({
    queryKey: ['item-suppliers', itemId],
    queryFn: () => fetchItemSuppliers(itemId!),
    enabled: itemId != null,
    staleTime: 60_000,
  })
}

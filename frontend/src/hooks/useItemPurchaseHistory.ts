import { useQuery } from '@tanstack/react-query'
import type { ItemPurchaseHistory } from '../types/api'
import { fetchWithAuth } from '../lib/api'

async function fetchItemPurchaseHistory(itemId: number): Promise<ItemPurchaseHistory> {
  const res = await fetchWithAuth(`/api/purchases/item/${itemId}`)
  if (!res.ok) throw new Error(`Item history fetch failed: ${res.status}`)
  return res.json() as Promise<ItemPurchaseHistory>
}

export function useItemPurchaseHistory(itemId: number | null) {
  return useQuery<ItemPurchaseHistory, Error>({
    queryKey: ['item-purchase-history', itemId],
    queryFn: () => fetchItemPurchaseHistory(itemId!),
    enabled: itemId !== null,
    staleTime: 60_000,
  })
}

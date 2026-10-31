import { useQuery } from '@tanstack/react-query'
import type { SupplierOption } from '../types/api'
import { fetchWithAuth } from '../lib/api'

async function fetchSuppliers(): Promise<SupplierOption[]> {
  const res = await fetchWithAuth('/api/suppliers')
  if (!res.ok) throw new Error(`Suppliers fetch failed: ${res.status}`)
  return res.json() as Promise<SupplierOption[]>
}

export function useSuppliers() {
  return useQuery<SupplierOption[], Error>({
    queryKey: ['suppliers'],
    queryFn: fetchSuppliers,
    staleTime: 5 * 60_000,  // suppliers change rarely
  })
}

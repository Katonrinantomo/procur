import { useQuery } from '@tanstack/react-query'
import type { SupplierOption } from '../types/api'

async function fetchSuppliers(): Promise<SupplierOption[]> {
  const res = await fetch('/api/suppliers')
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

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueueRow, Quotation, QuotationSummary } from '../types/api'
import { fetchWithAuth } from '../lib/api'

async function errorText(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // not JSON
  }
  return `Server error ${res.status}`
}

export function useQuotations() {
  return useQuery<QuotationSummary[], Error>({
    queryKey: ['quotations'],
    queryFn: async () => {
      const res = await fetchWithAuth('/api/quotations')
      if (!res.ok) throw new Error(await errorText(res))
      return res.json() as Promise<QuotationSummary[]>
    },
  })
}

export function useQuotation(id: number | null) {
  return useQuery<Quotation, Error>({
    queryKey: ['quotation', id],
    enabled: id !== null,
    queryFn: async () => {
      const res = await fetchWithAuth(`/api/quotations/${id}`)
      if (!res.ok) throw new Error(await errorText(res))
      return res.json() as Promise<Quotation>
    },
  })
}

export function useUploadQuotation() {
  const qc = useQueryClient()
  return useMutation<Quotation, Error, File>({
    mutationFn: async (file) => {
      const form = new FormData()
      form.append('file', file)
      const res = await fetchWithAuth('/api/quotations', { method: 'POST', body: form })
      if (!res.ok) throw new Error(await errorText(res))
      return res.json() as Promise<Quotation>
    },
    onSuccess: (q) => {
      qc.setQueryData(['quotation', q.id], q)
      void qc.invalidateQueries({ queryKey: ['quotations'] })
    },
  })
}

export function useQuotationToQueue() {
  const qc = useQueryClient()
  return useMutation<QueueRow[], Error, number>({
    mutationFn: async (id) => {
      const res = await fetchWithAuth(`/api/quotations/${id}/to-queue`, { method: 'POST' })
      if (!res.ok) throw new Error(await errorText(res))
      return res.json() as Promise<QueueRow[]>
    },
    onSuccess: (_rows, id) => {
      void qc.invalidateQueries({ queryKey: ['quotation', id] })
      void qc.invalidateQueries({ queryKey: ['quotations'] })
      void qc.invalidateQueries({ queryKey: ['queue'] })
    },
  })
}

/** TypeScript interfaces matching backend Pydantic schemas (backend/app/schemas.py). */

export interface QueueRow {
  id: number
  request_id: number
  line_no: number
  raw_name: string
  department: string | null
  qty: number | null
  unit: string | null
  quoted_unit_price_idr: number | null
  reference_unit_price_idr: number | null
  diff_pct: number | null
  checked_via: string | null
  history_count: number | null
  web_quote_count: number | null
  status: string
  requested_by: string | null
  requested_at: string  // ISO datetime string
  flag_codes: string[]
  risk_score: number
}

export interface StatusCounts {
  flagged: number
  new: number
  checked: number
  approved: number
  returned: number
  pending: number
}

export interface QueueResponse {
  rows: QueueRow[]
  counts: StatusCounts
}

export interface FlagOut {
  code: string
  message: string
}

export interface PurchaseOut {
  purchase_date: string  // ISO datetime string
  po_number: string | null
  supplier_name: string
  qty: number
  unit_price_idr: number
}

export interface WebQuoteOut {
  seller: string | null
  title: string | null
  url: string | null
  price_idr: number
  fetched_at: string  // ISO datetime string
}

export interface ActionOut {
  action: string
  note: string | null
  actor: string | null
  created_at: string
}

export interface LineItemDraft {
  name: string
  qty: number | null
  unit: string | null
  department: string | null
  quoted_unit_price_idr: number | null
  supplier: string | null
}

export interface RequestItemDetail {
  id: number
  request_id: number
  line_no: number
  catalog_item_id: number | null
  raw_name: string
  department: string | null
  qty: number | null
  unit: string | null
  quoted_unit_price_idr: number | null
  quoting_supplier_name: string | null
  reference_unit_price_idr: number | null
  diff_pct: number | null
  price_status?: string
  checked_via: string | null
  history_count: number | null
  usual_qty: number | null
  status: string
  risk_score: number
  check_error: string | null
  checked_at: string | null
  requested_by: string | null
  requested_at: string
  quoted_total_idr: number | null
  reference_total_idr: number | null
  over_reference_idr: number | null
  qty_on_hand: number | null
  avg_monthly_use: number | null
  flags: FlagOut[]
  last_purchases: PurchaseOut[] | null
  web_quotes: WebQuoteOut[] | null
  actions: ActionOut[]
  latest_audit_log?: AuditLogRow | null
}

export interface SupplierSummary {
  supplier_id: number
  supplier_name: string
  last_unit_price_idr: number
  last_purchase_date: string  // ISO datetime string
  buy_count: number
}

export interface SuppliersResponse {
  item_id: number
  item_name: string
  suppliers: SupplierSummary[]
}

// ---------------------------------------------------------------------------
// Purchases history
// ---------------------------------------------------------------------------

export interface PurchaseRow {
  id: number
  purchase_date: string  // ISO datetime string
  po_number: string | null
  item_id: number
  item_name: string
  supplier_id: number
  supplier_name: string
  qty: number
  unit: string
  unit_price_idr: number
  total_idr: number
}

export interface PurchasesResponse {
  rows: PurchaseRow[]
  total_count: number
  total_amount_idr: number
  page: number
  page_size: number
}

export interface SupplierOption {
  id: number
  name: string
}

export interface ItemPurchaseHistory {
  item_id: number
  item_name: string
  last_purchases: PurchaseRow[]
  reference_price_idr: number | null
}

// ---------------------------------------------------------------------------
// Request items list (History → Requests tab)
// ---------------------------------------------------------------------------

export interface RequestItemsListResponse {
  rows: QueueRow[]
  total_count: number
  page: number
  page_size: number
}

// ---------------------------------------------------------------------------
// Quick check (dry-run — no DB writes)
// ---------------------------------------------------------------------------

export interface QuickCheckResult {
  raw_name: string
  name: string
  catalog_item_id: number | null
  category: string | null
  qty: number | null
  unit: string | null
  department: string | null
  quoted_unit_price_idr: number | null
  quoting_supplier_name: string | null
  history_count: number
  last_purchases: PurchaseOut[]
  web_quotes: WebQuoteOut[]
  reference_unit_price_idr: number | null
  checked_via: string
  diff_pct: number | null
  flags: FlagOut[]
  status: string
  check_error: string | null
}

// ---------------------------------------------------------------------------
// Audit log
// ---------------------------------------------------------------------------

export interface AuditLogRow {
  id: number
  request_item_id: number | null
  item_name: string | null
  actor_role: string
  action: string
  note: string | null
  created_at: string
}

// ---------------------------------------------------------------------------
// Vendor quotations (M18) — band, recommendation and score come from Python
// ---------------------------------------------------------------------------

export type PriceBand = 'KOMPETITIF' | 'WAJAR' | 'PERHATIAN' | 'TIDAK WAJAR' | 'UNKNOWN'
export type Recommendation = 'SETUJU' | 'NEGOSIASI' | 'TOLAK'

export interface QuoteEvidence {
  title: string | null
  url: string | null
  seller: string | null
  price_idr: number
}

export interface QuoteDropped {
  title: string | null
  url: string | null
  price_idr: number
  reason: string
  reason_label: string
}

export interface QuotationLine {
  line_no: number
  name: string
  qty: number | null
  unit: string | null
  unit_price_idr: number | null
  line_total_idr: number | null
  catalog_item_id: number | null
  reference_unit_price_idr: number | null
  reference_source: 'history' | 'web' | 'none'
  history_count: number | null
  diff_pct: number | null
  band: PriceBand
  recommendation: Recommendation | null
  evidence: QuoteEvidence[]
  dropped: QuoteDropped[]
}

export interface Quotation {
  id: number
  filename: string
  status: 'pending' | 'checked' | 'unreadable' | 'queued'
  check_error: string | null
  vendor_name: string | null
  quote_no: string | null
  quote_date: string | null
  quote_total_idr: number | null
  vendor_score: number | null
  price_points: number | null
  arithmetic_ok: boolean | null
  covered_lines: number
  total_lines: number
  dropped_count: number
  dropped_summary: Record<string, number>
  request_id: number | null
  created_by_user_id: number | null
  created_at: string
  lines: QuotationLine[]
}

export interface QuotationSummary {
  id: number
  filename: string
  status: Quotation['status']
  vendor_name: string | null
  vendor_score: number | null
  created_at: string
}

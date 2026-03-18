/**
 * API client for the AP Invoice Processing backend.
 * All endpoints hit /api/* which is proxied to http://localhost:8000 by Vite.
 */

const BASE = '/api'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Vendor {
  vendor_id: string
  vendor_name: string
  address?: string
  tax_id?: string
  payment_terms: string
  bank_account?: string
  status: 'active' | 'inactive' | 'blocked'
  created_at?: string
}

export interface LineItem {
  description: string
  qty: number
  unit_price: number
  amount: number
}

export interface PurchaseOrder {
  po_number: string
  vendor_id: string
  po_date?: string
  total_amount: number
  currency: string
  line_items?: LineItem[]
  status: 'open' | 'partially_received' | 'closed'
  department?: string
  approver?: string
}

export interface Invoice {
  invoice_id: string
  vendor_id?: string
  po_number?: string
  invoice_number?: string
  invoice_date?: string
  total_amount?: number
  currency?: string
  extracted_fields?: Record<string, unknown>
  confidence_score?: number
  status: 'approved' | 'flagged_for_review' | 'rejected'
  decision_reason?: string
  pipeline_response?: string
  agent_trace?: AgentTraceItem[]
  processed_at?: string
}

export interface AgentTraceItem {
  type: 'tool_call' | 'tool_result' | 'message' | 'handoff'
  agent?: string
  tool?: string
  input?: Record<string, unknown>
  output?: string
  content?: string
  from_agent?: string
  to_agent?: string
  step?: number
}

export interface ReviewQueueItem {
  id: number
  invoice_id: string
  reason: string
  priority: 'low' | 'medium' | 'high'
  assigned_to?: string
  status: 'pending' | 'in_review' | 'resolved'
  notes?: string
  resolved_by?: string
  resolved_at?: string
  created_at?: string
  // Joined fields from processed_invoices
  invoice_number?: string
  vendor_id?: string
  total_amount?: number
  currency?: string
}

export interface VendorHistory {
  has_history: boolean
  vendor_id: string
  message?: string
  summary?: {
    total_invoices: number
    approved: number
    flagged: number
    rejected: number
    approval_rate_pct: number
    avg_invoice_amount: number
    min_invoice_amount: number
    max_invoice_amount: number
    avg_confidence_score: number
  }
  recent_invoices?: {
    invoice_id: string
    invoice_number?: string
    invoice_date?: string
    total_amount?: number
    status: string
    decision_reason?: string
    confidence_score?: number
    processed_at?: string
  }[]
  common_flag_reasons?: { reason: string; count: number }[]
  reviewer_notes?: {
    note: string
    resolved_by?: string
    resolved_at?: string
    original_flag_reason?: string
    invoice_number?: string
    invoice_amount?: number
  }[]
  interpretation?: string
}

export interface Stats {
  total_processed: number
  approved: number
  flagged_for_review: number
  rejected: number
  approval_rate: number
  avg_confidence_score: number
  common_flag_reasons: { reason: string; count: number }[]
}

// ─── SSE Event types ──────────────────────────────────────────────────────────

export type SSEEvent =
  | { event: 'upload_complete'; filename: string; file_path: string }
  | { event: 'agent_start'; agent: string; step: number }
  | { event: 'handoff'; from_agent: string; to_agent: string; step: number }
  | { event: 'tool_call'; agent: string; tool: string; input: Record<string, unknown>; step: number }
  | { event: 'tool_result'; agent: string; output: string; step: number }
  | { event: 'agent_message'; agent: string; message: string; step: number }
  | { event: 'pipeline_complete'; final_output: string; trace: AgentTraceItem[] }
  | { event: 'pipeline_error'; error: string; message: string }

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.statusText}`)
  return res.json()
}

// ─── API methods ──────────────────────────────────────────────────────────────

export const api = {
  /** Upload a PDF and process it via SSE streaming. Returns EventSource. */
  uploadInvoiceStream(file: File, onEvent: (e: SSEEvent) => void, onDone: () => void, onError: (e: string) => void) {
    const formData = new FormData()
    formData.append('file', file)

    // Use fetch + ReadableStream for SSE over POST
    fetch(`${BASE}/upload-invoice`, { method: 'POST', body: formData })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`)
        const reader = res.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6)) as SSEEvent
                onEvent(data)
                if (data.event === 'pipeline_complete' || data.event === 'pipeline_error') {
                  onDone()
                }
              } catch {
                // Ignore parse errors
              }
            }
          }
        }
        onDone()
      })
      .catch((e) => onError(String(e)))
  },

  chatStream(message: string, onEvent: (e: SSEEvent) => void, onDone: () => void, onError: (e: string) => void) {
    fetch(`${BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Chat failed: ${res.statusText}`)
        const reader = res.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6)) as SSEEvent
                onEvent(data)
                if (data.event === 'pipeline_complete' || data.event === 'pipeline_error') {
                  onDone()
                }
              } catch { /* skip */ }
            }
          }
        }
        onDone()
      })
      .catch((e) => onError(String(e)))
  },

  getInvoices: () => get<Invoice[]>('/invoices'),
  getInvoice: (id: string) => get<Invoice>(`/invoices/${id}`),
  getReviewQueue: (status = 'pending') => get<ReviewQueueItem[]>(`/review-queue?status=${status}`),

  resolveReviewItem: (id: number, resolution: 'approve' | 'reject', notes?: string, resolvedBy?: string) =>
    post<{ success: boolean; resolution: string; message: string }>(
      `/review-queue/${id}/resolve`,
      { resolution, notes, resolved_by: resolvedBy }
    ),

  getVendors: () => get<Vendor[]>('/vendors'),
  getPurchaseOrders: () => get<PurchaseOrder[]>('/purchase-orders'),
  getStats: () => get<Stats>('/stats'),
  getVendorHistory: (vendorId: string) => get<VendorHistory>(`/vendors/${vendorId}/history`),
  getLogs: (limit = 20) => get<{ available: boolean; traces: unknown[]; langfuse_url: string }>(`/logs?limit=${limit}`),
}

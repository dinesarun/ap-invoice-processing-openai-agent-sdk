import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, RefreshCw } from 'lucide-react'
import { api, Invoice } from '../api/client'
import clsx from 'clsx'

function StatusBadge({ status }: { status: Invoice['status'] }) {
  if (status === 'approved') return <span className="badge-green">✓ Approved</span>
  if (status === 'flagged_for_review') return <span className="badge-yellow">⚠ Review</span>
  return <span className="badge-red">✗ Rejected</span>
}

function ConfidenceBar({ score }: { score?: number }) {
  if (score == null) return <span className="text-slate-400 text-xs">—</span>
  const pct = Math.round(score * 100)
  const color = pct >= 80 ? 'bg-emerald-500' : pct >= 60 ? 'bg-amber-400' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-600">{pct}%</span>
    </div>
  )
}

function TraceViewer({ trace }: { trace: unknown[] }) {
  return (
    <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-3">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Agent Trace</p>
      {trace.map((item: unknown, i) => {
        const t = item as { type: string; agent?: string; tool?: string; input?: unknown; output?: string; content?: string }
        return (
          <div key={i} className="text-xs font-mono bg-slate-50 rounded p-2 space-y-0.5">
            <span className={clsx(
              'font-semibold',
              t.type === 'tool_call' && 'text-blue-600',
              t.type === 'tool_result' && 'text-emerald-600',
              t.type === 'message' && 'text-slate-600',
            )}>
              [{t.type}]
            </span>
            {t.agent && <span className="text-slate-500 ml-1">• {t.agent}</span>}
            {t.tool && <span className="text-purple-600 ml-1">→ {t.tool}</span>}
            {t.content && (
              <div className="text-slate-600 whitespace-pre-wrap">{String(t.content).slice(0, 200)}</div>
            )}
            {t.output && (
              <div className="text-slate-500 whitespace-pre-wrap">{String(t.output).slice(0, 200)}</div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function InvoiceRow({ invoice }: { invoice: Invoice }) {
  const [expanded, setExpanded] = useState(false)
  const fields = invoice.extracted_fields as Record<string, unknown> | undefined

  return (
    <div className="card overflow-hidden">
      <button
        className="w-full flex items-center gap-4 p-4 text-left hover:bg-slate-50 transition-colors"
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex-1 min-w-0 grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <p className="text-xs text-slate-400">Invoice #</p>
            <p className="font-medium text-slate-900 truncate">{invoice.invoice_number || invoice.invoice_id}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Vendor</p>
            <p className="text-sm text-slate-700 truncate">
              {(fields?.vendor_name as string) || invoice.vendor_id || '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Amount</p>
            <p className="text-sm font-medium text-slate-900">
              {invoice.total_amount != null
                ? `$${invoice.total_amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
                : '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Status</p>
            <StatusBadge status={invoice.status} />
          </div>
        </div>
        <div className="hidden md:flex flex-col items-end gap-1 flex-shrink-0">
          <ConfidenceBar score={invoice.confidence_score} />
          <p className="text-xs text-slate-400">
            {invoice.processed_at ? new Date(invoice.processed_at).toLocaleDateString() : ''}
          </p>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-slate-400 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-100">
          <div className="mt-3 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            <div><span className="text-slate-400">Invoice ID: </span><span className="font-mono text-xs">{invoice.invoice_id}</span></div>
            <div><span className="text-slate-400">PO #: </span>{invoice.po_number || '—'}</div>
            <div><span className="text-slate-400">Date: </span>{invoice.invoice_date || '—'}</div>
            <div><span className="text-slate-400">Vendor ID: </span>{invoice.vendor_id || '—'}</div>
            <div><span className="text-slate-400">Currency: </span>{invoice.currency || 'USD'}</div>
          </div>

          {invoice.decision_reason && (
            <div className={clsx(
              'mt-3 text-sm rounded-lg p-3',
              invoice.status === 'approved' ? 'bg-emerald-50 text-emerald-800' :
              invoice.status === 'rejected' ? 'bg-red-50 text-red-800' : 'bg-amber-50 text-amber-800'
            )}>
              <span className="font-medium">Decision: </span>{invoice.decision_reason}
            </div>
          )}

          {Array.isArray(invoice.agent_trace) && invoice.agent_trace.length > 0 && (
            <TraceViewer trace={invoice.agent_trace} />
          )}
        </div>
      )}
    </div>
  )
}

export default function InvoiceList() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | Invoice['status']>('all')

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.getInvoices()
      setInvoices(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filtered = filter === 'all' ? invoices : invoices.filter((i) => i.status === filter)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Processed Invoices</h1>
          <p className="text-sm text-slate-500 mt-1">{invoices.length} total</p>
        </div>
        <button onClick={load} className="btn-secondary">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {(['all', 'approved', 'flagged_for_review', 'rejected'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              filter === f
                ? 'bg-blue-600 text-white'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            )}
          >
            {f === 'all' ? 'All' : f === 'flagged_for_review' ? 'Flagged' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading invoices…</div>
      ) : filtered.length === 0 ? (
        <div className="card p-12 text-center text-slate-400">
          No invoices found. Upload a PDF to get started.
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((inv) => <InvoiceRow key={inv.invoice_id} invoice={inv} />)}
        </div>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import {
  ChevronDown, ChevronUp, RefreshCw, CheckCircle2, AlertTriangle,
  XCircle, Bot, Wrench, MessageSquare, FileText, ChevronRight,
} from 'lucide-react'
import { api, Invoice, AgentTraceItem } from '../api/client'
import VendorContextPanel from './VendorContextPanel'
import clsx from 'clsx'

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: Invoice['status'] }) {
  if (status === 'approved') return <span className="badge-green">✓ Approved</span>
  if (status === 'flagged_for_review') return <span className="badge-yellow">⚠ Review</span>
  return <span className="badge-red">✗ Rejected</span>
}

// ─── Confidence bar ───────────────────────────────────────────────────────────

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

// ─── Decision banner (top of expanded view) ───────────────────────────────────

function DecisionBanner({ invoice }: { invoice: Invoice }) {
  const approved = invoice.status === 'approved'
  const flagged  = invoice.status === 'flagged_for_review'

  const bg      = approved ? 'bg-emerald-50  border-emerald-200' : flagged ? 'bg-amber-50  border-amber-200'  : 'bg-red-50  border-red-200'
  const heading = approved ? 'text-emerald-800' : flagged ? 'text-amber-800' : 'text-red-800'
  const sub     = approved ? 'text-emerald-700' : flagged ? 'text-amber-700' : 'text-red-700'
  const Icon    = approved ? CheckCircle2 : flagged ? AlertTriangle : XCircle
  const iconCol = approved ? 'text-emerald-500' : flagged ? 'text-amber-500' : 'text-red-500'
  const label   = approved ? 'Auto-Approved' : flagged ? 'Flagged for Human Review' : 'Rejected'

  return (
    <div className={clsx('rounded-xl border p-4 flex gap-3', bg)}>
      <Icon className={clsx('w-5 h-5 flex-shrink-0 mt-0.5', iconCol)} />
      <div>
        <p className={clsx('font-semibold text-sm', heading)}>{label}</p>
        {invoice.decision_reason && (
          <p className={clsx('text-sm mt-0.5', sub)}>{invoice.decision_reason}</p>
        )}
        <div className="flex items-center gap-4 mt-2 flex-wrap">
          {invoice.confidence_score != null && (
            <span className="text-xs text-slate-500">
              Extraction confidence: <strong>{Math.round(invoice.confidence_score * 100)}%</strong>
            </span>
          )}
          {invoice.processed_at && (
            <span className="text-xs text-slate-400">
              Processed {new Date(invoice.processed_at).toLocaleString()}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Pipeline complete response ───────────────────────────────────────────────

function PipelineResponse({ text }: { text: string }) {
  const [collapsed, setCollapsed] = useState(true)
  const preview = text.slice(0, 280)
  const hasMore = text.length > 280

  return (
    <div className="rounded-xl border border-blue-200 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-blue-50 border-b border-blue-100">
        <Bot className="w-4 h-4 text-blue-600 flex-shrink-0" />
        <span className="text-xs font-semibold text-blue-800 uppercase tracking-wide">
          Pipeline Complete — Agent Response
        </span>
        <span className="text-xs text-blue-500 ml-auto">Full reasoning output</span>
      </div>
      <div className="px-4 py-3 bg-white">
        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
          {collapsed && hasMore ? preview + '…' : text}
        </p>
        {hasMore && (
          <button
            onClick={() => setCollapsed(c => !c)}
            className="mt-2 text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            {collapsed ? 'Show full response ↓' : 'Collapse ↑'}
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Agent journey timeline ───────────────────────────────────────────────────

const AGENT_ORDER = [
  'Triage Agent',
  'Extraction Agent',
  'Vendor Lookup Agent',
  'PO Matching Agent',
  'Decision Agent',
]

const AGENT_ICONS: Record<string, string> = {
  'Triage Agent':        '🚦',
  'Extraction Agent':    '🔍',
  'Vendor Lookup Agent': '🏢',
  'PO Matching Agent':   '📋',
  'Decision Agent':      '⚖️',
}

function AgentJourney({ trace }: { trace: AgentTraceItem[] }) {
  const [expanded, setExpanded] = useState<string | null>(null)

  // Group trace items by agent
  const byAgent: Record<string, AgentTraceItem[]> = {}
  for (const item of trace) {
    const agent = item.agent || 'Unknown'
    if (!byAgent[agent]) byAgent[agent] = []
    byAgent[agent].push(item)
  }

  // Get the agents that actually appear in the trace, in pipeline order
  const agents = AGENT_ORDER.filter(a => byAgent[a])
  if (agents.length === 0) return null

  return (
    <div className="rounded-xl border border-slate-200 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-50 border-b border-slate-200">
        <ChevronRight className="w-4 h-4 text-slate-400" />
        <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
          Agent Pipeline Journey
        </span>
        <span className="text-xs text-slate-400 ml-auto">
          {agents.length} agents ran
        </span>
      </div>

      <div className="divide-y divide-slate-100">
        {agents.map((agentName, i) => {
          const items = byAgent[agentName] || []
          const isOpen = expanded === agentName

          // Extract the most meaningful message for the summary line
          const messageItem = items.find(it => it.type === 'message' && it.content)
          const toolCalls   = items.filter(it => it.type === 'tool_call')
          const summary     = messageItem?.content?.slice(0, 140) || null

          return (
            <div key={agentName}>
              <button
                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors"
                onClick={() => setExpanded(isOpen ? null : agentName)}
              >
                {/* Step number + icon */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-500">
                    {i + 1}
                  </span>
                  <span className="text-base">{AGENT_ICONS[agentName] || '🤖'}</span>
                </div>

                {/* Agent name + summary */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800">{agentName}</p>
                  {summary && (
                    <p className="text-xs text-slate-500 truncate mt-0.5">{summary}</p>
                  )}
                </div>

                {/* Tool call pills */}
                <div className="hidden md:flex items-center gap-1 flex-shrink-0">
                  {toolCalls.map((tc, j) => (
                    <span key={j} className="text-xs bg-purple-50 text-purple-700 border border-purple-100 rounded px-1.5 py-0.5">
                      {tc.tool}
                    </span>
                  ))}
                </div>

                {isOpen
                  ? <ChevronUp className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  : <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
                }
              </button>

              {isOpen && (
                <div className="px-4 pb-4 space-y-2 bg-slate-50/50">
                  {items.map((item, j) => {
                    if (item.type === 'tool_call') {
                      return (
                        <div key={j} className="flex items-start gap-2">
                          <Wrench className="w-3.5 h-3.5 text-purple-400 flex-shrink-0 mt-1" />
                          <div className="text-xs">
                            <span className="font-medium text-purple-700">Called: </span>
                            <span className="font-mono text-purple-600">{item.tool}</span>
                            {item.input && (
                              <div className="mt-1 text-slate-500 font-mono bg-white rounded border border-slate-100 px-2 py-1 overflow-x-auto whitespace-nowrap max-w-sm">
                                {JSON.stringify(item.input).slice(0, 180)}
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    }
                    if (item.type === 'tool_result') {
                      return (
                        <div key={j} className="flex items-start gap-2">
                          <span className="text-emerald-400 text-xs flex-shrink-0 mt-0.5 font-bold">↩</span>
                          <p className="text-xs text-slate-600 font-mono bg-white rounded border border-slate-100 px-2 py-1 whitespace-pre-wrap break-all max-w-sm">
                            {String(item.output || '').slice(0, 300)}
                          </p>
                        </div>
                      )
                    }
                    if (item.type === 'message' && item.content) {
                      return (
                        <div key={j} className="flex items-start gap-2">
                          <MessageSquare className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mt-1" />
                          <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap">
                            {String(item.content).slice(0, 600)}
                          </p>
                        </div>
                      )
                    }
                    return null
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Extracted fields grid ────────────────────────────────────────────────────

function ExtractedFields({ fields }: { fields: Record<string, unknown> }) {
  const SKIP = ['line_items', 'bill_to']
  const LABELS: Record<string, string> = {
    vendor_name: 'Vendor', vendor_address: 'Address', vendor_tax_id: 'Tax ID',
    invoice_number: 'Invoice #', invoice_date: 'Invoice Date', due_date: 'Due Date',
    payment_terms: 'Payment Terms', po_number: 'PO #', subtotal: 'Subtotal',
    tax_amount: 'Tax', tax_rate: 'Tax Rate', total_amount: 'Total',
    currency: 'Currency',
  }

  const entries = Object.entries(fields)
    .filter(([k, v]) => !SKIP.includes(k) && v != null && v !== '')
    .map(([k, v]) => [LABELS[k] || k, v] as [string, unknown])

  if (entries.length === 0) return null

  return (
    <div className="rounded-xl border border-slate-200 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-50 border-b border-slate-200">
        <FileText className="w-4 h-4 text-slate-400" />
        <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
          Extracted Invoice Fields
        </span>
      </div>
      <div className="p-4 grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3">
        {entries.map(([label, value]) => (
          <div key={label}>
            <p className="text-xs text-slate-400">{label}</p>
            <p className="text-sm font-medium text-slate-800 truncate">{String(value)}</p>
          </div>
        ))}
      </div>
      {/* Line items if present */}
      {Array.isArray(fields.line_items) && fields.line_items.length > 0 && (
        <div className="border-t border-slate-100 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-50">
                <th className="text-left px-4 py-2 text-slate-500 font-medium">Description</th>
                <th className="text-center px-4 py-2 text-slate-500 font-medium">Qty</th>
                <th className="text-right px-4 py-2 text-slate-500 font-medium">Unit Price</th>
                <th className="text-right px-4 py-2 text-slate-500 font-medium">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(fields.line_items as Record<string, unknown>[]).map((li, i) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="px-4 py-2 text-slate-700">{String(li.description || '')}</td>
                  <td className="px-4 py-2 text-center text-slate-600">{String(li.qty || '')}</td>
                  <td className="px-4 py-2 text-right text-slate-600">
                    {li.unit_price != null ? `$${Number(li.unit_price).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
                  </td>
                  <td className="px-4 py-2 text-right font-medium text-slate-800">
                    {li.amount != null ? `$${Number(li.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ─── Invoice row ──────────────────────────────────────────────────────────────

function InvoiceRow({ invoice }: { invoice: Invoice }) {
  const [expanded, setExpanded] = useState(false)
  const fields = invoice.extracted_fields as Record<string, unknown> | undefined

  return (
    <div className="card overflow-hidden">
      {/* Summary row — click to expand */}
      <button
        className="w-full flex items-center gap-4 p-4 text-left hover:bg-slate-50 transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        <div className="flex-1 min-w-0 grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <p className="text-xs text-slate-400">Invoice #</p>
            <p className="font-medium text-slate-900 truncate">
              {invoice.invoice_number || invoice.invoice_id}
            </p>
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
        {expanded
          ? <ChevronUp className="w-4 h-4 text-slate-400 flex-shrink-0" />
          : <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />}
      </button>

      {/* Expanded detail view */}
      {expanded && (
        <div className="border-t border-slate-100 px-4 pb-6 pt-4 space-y-4">

          {/* 1. Decision banner — the verdict, front and centre */}
          <DecisionBanner invoice={invoice} />

          {/* 2. Pipeline Complete — Agent Response */}
          {invoice.pipeline_response && (
            <PipelineResponse text={invoice.pipeline_response} />
          )}

          {/* 3. Extracted invoice fields */}
          {fields && Object.keys(fields).length > 0 && (
            <ExtractedFields fields={fields} />
          )}

          {/* 4. Metadata strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2 text-sm px-1">
            <div><span className="text-slate-400 text-xs">Invoice ID </span><br /><span className="font-mono text-xs text-slate-600">{invoice.invoice_id}</span></div>
            <div><span className="text-slate-400 text-xs">PO # </span><br /><span className="text-slate-700">{invoice.po_number || '—'}</span></div>
            <div><span className="text-slate-400 text-xs">Vendor ID </span><br /><span className="text-slate-700">{invoice.vendor_id || '—'}</span></div>
            <div><span className="text-slate-400 text-xs">Currency </span><br /><span className="text-slate-700">{invoice.currency || 'USD'}</span></div>
          </div>

          {/* 5. Agent pipeline journey */}
          {Array.isArray(invoice.agent_trace) && invoice.agent_trace.length > 0 && (
            <AgentJourney trace={invoice.agent_trace} />
          )}

          {/* 6. Vendor context panel */}
          {invoice.vendor_id && (
            <VendorContextPanel
              vendorId={invoice.vendor_id}
              currentAmount={invoice.total_amount}
            />
          )}
        </div>
      )}
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function InvoiceList() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | Invoice['status']>('all')

  const load = async () => {
    setLoading(true)
    try {
      setInvoices(await api.getInvoices())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const counts = {
    all: invoices.length,
    approved: invoices.filter(i => i.status === 'approved').length,
    flagged_for_review: invoices.filter(i => i.status === 'flagged_for_review').length,
    rejected: invoices.filter(i => i.status === 'rejected').length,
  }
  const filtered = filter === 'all' ? invoices : invoices.filter(i => i.status === filter)

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

      {/* Filter tabs with counts */}
      <div className="flex gap-2">
        {([
          { key: 'all',               label: 'All' },
          { key: 'approved',          label: 'Approved' },
          { key: 'flagged_for_review', label: 'Flagged' },
          { key: 'rejected',          label: 'Rejected' },
        ] as const).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              filter === key
                ? 'bg-blue-600 text-white'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            )}
          >
            {label}
            <span className={clsx(
              'text-xs rounded-full px-1.5 py-0.5 font-semibold',
              filter === key ? 'bg-blue-500 text-white' : 'bg-slate-100 text-slate-500'
            )}>
              {counts[key]}
            </span>
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
          {filtered.map(inv => <InvoiceRow key={inv.invoice_id} invoice={inv} />)}
        </div>
      )}
    </div>
  )
}

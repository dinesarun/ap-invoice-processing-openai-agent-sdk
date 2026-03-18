import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, XCircle, RefreshCw, Clock, ChevronDown, ChevronUp, User, FileText } from 'lucide-react'
import { api, ReviewQueueItem } from '../api/client'
import clsx from 'clsx'

function PriorityBadge({ priority }: { priority: ReviewQueueItem['priority'] }) {
  if (priority === 'high') return <span className="badge-red">High</span>
  if (priority === 'medium') return <span className="badge-yellow">Medium</span>
  return <span className="badge-gray">Low</span>
}

function ResolutionBadge({ status }: { status?: string }) {
  if (status === 'approved') return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
      <CheckCircle2 className="w-3 h-3" /> Approved
    </span>
  )
  if (status === 'rejected') return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200">
      <XCircle className="w-3 h-3" /> Rejected
    </span>
  )
  return <span className="badge-green">Resolved</span>
}

// ─── Resolve Modal ────────────────────────────────────────────────────────────

interface ResolveModalProps {
  item: ReviewQueueItem
  onClose: () => void
  onResolved: () => void
}

function ResolveModal({ item, onClose, onResolved }: ResolveModalProps) {
  const [notes, setNotes] = useState('')
  const [resolvedBy, setResolvedBy] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const resolve = async (resolution: 'approve' | 'reject') => {
    setSubmitting(true)
    try {
      await api.resolveReviewItem(item.id, resolution, notes, resolvedBy || 'AP Reviewer')
      onResolved()
    } catch (e) {
      alert('Failed to resolve: ' + String(e))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-md p-6 space-y-4">
        <h3 className="font-semibold text-slate-900">Review Invoice</h3>

        <div className="bg-slate-50 rounded-lg p-3 text-sm space-y-1">
          <div><span className="text-slate-400">Invoice #: </span><span>{item.invoice_number || item.invoice_id}</span></div>
          <div><span className="text-slate-400">Vendor: </span><span>{item.vendor_id || '—'}</span></div>
          <div><span className="text-slate-400">Amount: </span>
            <span>{item.total_amount != null ? `$${item.total_amount.toLocaleString()}` : '—'}</span>
          </div>
          <div className="pt-1 border-t border-slate-200">
            <span className="text-slate-400">Flag reason: </span>
            <span className="text-amber-700">{item.reason}</span>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Reviewer name</label>
          <input
            type="text"
            value={resolvedBy}
            onChange={(e) => setResolvedBy(e.target.value)}
            placeholder="Your name"
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Notes (optional)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add any notes about your decision…"
            rows={3}
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
        </div>

        <div className="flex gap-3">
          <button onClick={() => resolve('approve')} disabled={submitting} className="btn-success flex-1 justify-center">
            <CheckCircle2 className="w-4 h-4" />
            Approve
          </button>
          <button onClick={() => resolve('reject')} disabled={submitting} className="btn-danger flex-1 justify-center">
            <XCircle className="w-4 h-4" />
            Reject
          </button>
          <button onClick={onClose} disabled={submitting} className="btn-secondary">Cancel</button>
        </div>
      </div>
    </div>
  )
}

// ─── Queue Item Card ──────────────────────────────────────────────────────────

function QueueCard({
  item,
  onReview,
}: {
  item: ReviewQueueItem
  onReview?: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const isResolved = item.status === 'resolved'
  const currency = item.currency || '$'
  const amount = item.total_amount != null
    ? `${currency === 'USD' || currency === '$' ? '$' : currency + ' '}${item.total_amount.toLocaleString()}`
    : '—'

  return (
    <div className={clsx(
      'bg-white border rounded-xl transition-all duration-150',
      isResolved ? 'border-slate-200' : 'border-amber-200 shadow-sm',
    )}>
      {/* Always-visible row */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <AlertTriangle className={clsx('w-4 h-4 flex-shrink-0', isResolved ? 'text-slate-300' : 'text-amber-400')} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-slate-900 text-sm">
              {item.invoice_number || item.invoice_id}
            </span>
            <PriorityBadge priority={item.priority} />
            {isResolved && <ResolutionBadge status={item.invoice_status} />}
          </div>
          <p className="text-xs text-slate-400 mt-0.5 truncate">
            {item.vendor_id || 'Unknown vendor'} · {amount}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {!isResolved && onReview && (
            <button
              onClick={(e) => { e.stopPropagation(); onReview() }}
              className="btn-primary text-xs py-1 px-3"
            >
              Review
            </button>
          )}
          {expanded
            ? <ChevronUp className="w-4 h-4 text-slate-400" />
            : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </div>
      </div>

      {/* Expanded detail panel */}
      {expanded && (
        <div className="border-t border-slate-100 px-4 py-3 space-y-3">
          {/* Flag reason */}
          <div className="flex gap-2 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800 leading-relaxed">{item.reason}</p>
          </div>

          {/* Resolution detail — only for resolved items */}
          {isResolved && (
            <div className={clsx(
              'rounded-lg px-3 py-2.5 space-y-1.5 border text-xs',
              item.invoice_status === 'approved'
                ? 'bg-emerald-50 border-emerald-100'
                : item.invoice_status === 'rejected'
                  ? 'bg-red-50 border-red-100'
                  : 'bg-slate-50 border-slate-100',
            )}>
              <p className={clsx(
                'font-medium',
                item.invoice_status === 'approved' ? 'text-emerald-700'
                  : item.invoice_status === 'rejected' ? 'text-red-700'
                  : 'text-slate-600',
              )}>
                {item.invoice_status === 'approved' ? '✓ Approved by reviewer'
                  : item.invoice_status === 'rejected' ? '✗ Rejected by reviewer'
                  : 'Resolved'}
              </p>
              {item.notes && (
                <div className="flex gap-1.5 text-slate-600">
                  <FileText className="w-3 h-3 flex-shrink-0 mt-0.5" />
                  <span className="italic">"{item.notes}"</span>
                </div>
              )}
              <div className="flex items-center gap-3 text-slate-400 pt-0.5">
                {item.resolved_by && (
                  <span className="flex items-center gap-1">
                    <User className="w-3 h-3" />
                    {item.resolved_by}
                  </span>
                )}
                {item.resolved_at && (
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(item.resolved_at).toLocaleString()}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Flagged at */}
          {!isResolved && item.created_at && (
            <p className="flex items-center gap-1.5 text-xs text-slate-400">
              <Clock className="w-3 h-3" />
              Flagged {new Date(item.created_at).toLocaleString()}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function ReviewQueue() {
  const [items, setItems] = useState<ReviewQueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<'pending' | 'resolved'>('pending')
  const [resolveItem, setResolveItem] = useState<ReviewQueueItem | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.getReviewQueue(statusFilter)
      setItems(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [statusFilter])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Review Queue</h1>
          <p className="text-sm text-slate-500 mt-1">Human-in-the-loop review for flagged invoices</p>
        </div>
        <button onClick={load} className="btn-secondary">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Status filter */}
      <div className="flex gap-2">
        {(['pending', 'resolved'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize',
              statusFilter === s
                ? 'bg-blue-600 text-white'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            )}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Concept callout */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-amber-800">
          <strong>Human-in-the-Loop:</strong> When agents are uncertain (vendor mismatch, amount variance,
          missing PO), they flag the invoice here rather than making an autonomous decision.
          Reviewers provide the human judgment the AI deferred on.
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="card p-12 text-center">
          <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
          <p className="text-slate-500">No {statusFilter} items in the review queue.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <QueueCard
              key={item.id}
              item={item}
              onReview={item.status === 'pending' ? () => setResolveItem(item) : undefined}
            />
          ))}
        </div>
      )}

      {resolveItem && (
        <ResolveModal
          item={resolveItem}
          onClose={() => setResolveItem(null)}
          onResolved={() => { setResolveItem(null); load() }}
        />
      )}
    </div>
  )
}

/**
 * VendorContextPanel — shows the operational history the Decision Agent
 * used when processing an invoice. This makes the "Context as Moat" idea
 * tangible: the panel grows richer with every invoice processed.
 *
 * Rendered inside the expanded InvoiceRow when a vendor_id is present.
 */
import { useEffect, useState } from 'react'
import { TrendingUp, MessageSquare, AlertTriangle, Loader2, History, ChevronDown, ChevronUp } from 'lucide-react'
import { api, VendorHistory } from '../api/client'
import clsx from 'clsx'

function ApprovalRateBar({ rate }: { rate: number }) {
  const color = rate >= 90 ? 'bg-emerald-500' : rate >= 70 ? 'bg-amber-400' : 'bg-red-500'
  const label = rate >= 90 ? 'text-emerald-700' : rate >= 70 ? 'text-amber-700' : 'text-red-700'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${rate}%` }} />
      </div>
      <span className={`text-xs font-semibold ${label} w-10 text-right`}>{rate}%</span>
    </div>
  )
}

function AmountRange({ min, avg, max, current }: { min: number; avg: number; max: number; current?: number }) {
  const isAnomaly = current != null && current > max * 1.5
  const isHigh = current != null && current > max && !isAnomaly
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-400">
        <span>${min.toLocaleString()}</span>
        <span className="text-slate-500">avg ${avg.toLocaleString()}</span>
        <span>${max.toLocaleString()}</span>
      </div>
      <div className="relative h-2 bg-slate-100 rounded-full">
        {/* Range bar */}
        <div
          className="absolute h-full bg-blue-100 rounded-full"
          style={{ left: 0, right: 0 }}
        />
        {/* Avg marker */}
        <div
          className="absolute w-0.5 h-3 bg-blue-400 rounded-full -top-0.5"
          style={{ left: `${Math.min(((avg - min) / Math.max(max - min, 1)) * 100, 100)}%` }}
        />
        {/* Current invoice marker */}
        {current != null && (
          <div
            className={clsx(
              'absolute w-2 h-2 rounded-full border-2 border-white -top-0 shadow-sm',
              isAnomaly ? 'bg-red-500' : isHigh ? 'bg-amber-400' : 'bg-emerald-500'
            )}
            style={{ left: `${Math.min(((current - min) / Math.max(max - min, 1)) * 100, 95)}%` }}
            title={`This invoice: $${current.toLocaleString()}`}
          />
        )}
      </div>
      {current != null && (
        <p className={clsx(
          'text-xs',
          isAnomaly ? 'text-red-600 font-medium' : isHigh ? 'text-amber-600' : 'text-emerald-600'
        )}>
          This invoice: ${current.toLocaleString()}
          {isAnomaly ? ' — ⚠ significantly above historical max' : isHigh ? ' — above historical max' : ' — within normal range'}
        </p>
      )}
    </div>
  )
}

interface Props {
  vendorId: string
  currentAmount?: number
}

export default function VendorContextPanel({ vendorId, currentAmount }: Props) {
  const [history, setHistory] = useState<VendorHistory | null>(null)
  const [loading, setLoading] = useState(false)
  const [notesExpanded, setNotesExpanded] = useState(false)
  const [recentExpanded, setRecentExpanded] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.getVendorHistory(vendorId)
      .then(setHistory)
      .catch(() => setHistory({ has_history: false, vendor_id: vendorId }))
      .finally(() => setLoading(false))
  }, [vendorId])

  if (loading) {
    return (
      <div className="mt-4 border-t border-slate-100 pt-4 flex items-center gap-2 text-slate-400 text-sm">
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading vendor context…
      </div>
    )
  }

  if (!history) return null

  return (
    <div className="mt-4 border-t border-slate-100 pt-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <History className="w-4 h-4 text-blue-500" />
        <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
          Vendor Context — what the agent knew
        </span>
        <span className="text-xs text-slate-400 ml-auto">
          Powers the Decision Agent's historical reasoning
        </span>
      </div>

      {!history.has_history ? (
        <div className="bg-slate-50 rounded-lg p-3 text-sm text-slate-500 italic">
          {history.message || 'No prior invoices on record for this vendor.'}
        </div>
      ) : (
        <div className="space-y-4">

          {/* Interpretation — the plain-English summary the agent sees */}
          {history.interpretation && (
            <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-sm text-blue-800">
              <span className="font-medium">Agent interpretation: </span>
              {history.interpretation}
            </div>
          )}

          {/* Stats row */}
          {history.summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-xs text-slate-400">Total invoices</p>
                <p className="text-xl font-bold text-slate-900">{history.summary.total_invoices}</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-xs text-slate-400 mb-1">Approval rate</p>
                <ApprovalRateBar rate={history.summary.approval_rate_pct} />
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-xs text-slate-400">Flagged</p>
                <p className="text-xl font-bold text-amber-600">{history.summary.flagged}</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-xs text-slate-400">Avg confidence</p>
                <p className="text-xl font-bold text-slate-900">
                  {Math.round(history.summary.avg_confidence_score * 100)}%
                </p>
              </div>
            </div>
          )}

          {/* Amount range */}
          {history.summary && (
            <div className="bg-slate-50 rounded-lg p-3">
              <p className="text-xs font-medium text-slate-500 mb-2 flex items-center gap-1">
                <TrendingUp className="w-3.5 h-3.5" />
                Historical invoice amount range
              </p>
              <AmountRange
                min={history.summary.min_invoice_amount}
                avg={history.summary.avg_invoice_amount}
                max={history.summary.max_invoice_amount}
                current={currentAmount}
              />
            </div>
          )}

          {/* Common flag reasons */}
          {history.common_flag_reasons && history.common_flag_reasons.length > 0 && (
            <div className="bg-amber-50 rounded-lg p-3">
              <p className="text-xs font-medium text-amber-700 mb-2 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                Common flag reasons for this vendor
              </p>
              <div className="space-y-1">
                {history.common_flag_reasons.map((r, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-amber-800">
                    <span className="w-4 h-4 rounded-full bg-amber-200 flex items-center justify-center text-amber-700 font-bold flex-shrink-0">
                      {r.count}
                    </span>
                    <span>{r.reason}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Reviewer notes — the highest-value signal */}
          {history.reviewer_notes && history.reviewer_notes.length > 0 && (
            <div className="rounded-lg border border-emerald-200 overflow-hidden">
              <button
                className="w-full flex items-center gap-2 px-3 py-2.5 bg-emerald-50 text-left"
                onClick={() => setNotesExpanded(e => !e)}
              >
                <MessageSquare className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span className="text-xs font-semibold text-emerald-800">
                  Human reviewer notes ({history.reviewer_notes.length})
                </span>
                <span className="text-xs text-emerald-600 ml-1">— high-signal precedent for the agent</span>
                <span className="ml-auto">
                  {notesExpanded
                    ? <ChevronUp className="w-4 h-4 text-emerald-500" />
                    : <ChevronDown className="w-4 h-4 text-emerald-500" />}
                </span>
              </button>

              {notesExpanded && (
                <div className="divide-y divide-emerald-100">
                  {history.reviewer_notes.map((n, i) => (
                    <div key={i} className="p-3 bg-white text-sm space-y-1">
                      <div className="flex items-start gap-2">
                        <span className="text-emerald-500 mt-0.5 flex-shrink-0">"</span>
                        <p className="text-slate-700 italic flex-1">{n.note}</p>
                      </div>
                      <div className="text-xs text-slate-400 pl-3 space-x-3">
                        {n.resolved_by && <span>— {n.resolved_by}</span>}
                        {n.invoice_number && <span>on {n.invoice_number}</span>}
                        {n.invoice_amount && <span>${n.invoice_amount.toLocaleString()}</span>}
                        {n.resolved_at && (
                          <span>{new Date(n.resolved_at).toLocaleDateString()}</span>
                        )}
                      </div>
                      {n.original_flag_reason && (
                        <p className="text-xs text-amber-600 pl-3">
                          Originally flagged: "{n.original_flag_reason}"
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Recent invoices */}
          {history.recent_invoices && history.recent_invoices.length > 0 && (
            <div className="rounded-lg border border-slate-200 overflow-hidden">
              <button
                className="w-full flex items-center gap-2 px-3 py-2.5 bg-slate-50 text-left"
                onClick={() => setRecentExpanded(e => !e)}
              >
                <History className="w-4 h-4 text-slate-400 flex-shrink-0" />
                <span className="text-xs font-medium text-slate-600">
                  Recent invoices ({history.recent_invoices.length})
                </span>
                <span className="ml-auto">
                  {recentExpanded
                    ? <ChevronUp className="w-4 h-4 text-slate-400" />
                    : <ChevronDown className="w-4 h-4 text-slate-400" />}
                </span>
              </button>
              {recentExpanded && (
                <div className="divide-y divide-slate-100">
                  {history.recent_invoices.map((inv) => (
                    <div key={inv.invoice_id} className="px-3 py-2 flex items-center gap-3 text-xs bg-white">
                      <span className="font-mono text-slate-500 flex-shrink-0">
                        {inv.invoice_number || inv.invoice_id}
                      </span>
                      <span className="text-slate-700 flex-shrink-0">
                        {inv.total_amount != null ? `$${inv.total_amount.toLocaleString()}` : '—'}
                      </span>
                      <span className={clsx(
                        'px-1.5 py-0.5 rounded-full font-medium flex-shrink-0',
                        inv.status === 'approved' ? 'bg-emerald-100 text-emerald-700' :
                        inv.status === 'rejected' ? 'bg-red-100 text-red-700' :
                        'bg-amber-100 text-amber-700'
                      )}>
                        {inv.status === 'flagged_for_review' ? 'flagged' : inv.status}
                      </span>
                      {inv.decision_reason && (
                        <span className="text-slate-400 truncate">{inv.decision_reason}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

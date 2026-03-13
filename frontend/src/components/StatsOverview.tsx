import { Fragment, type ReactNode, useEffect, useState } from 'react'
import { CheckCircle2, AlertTriangle, FileText, TrendingUp, RefreshCw } from 'lucide-react'
import { api, Stats } from '../api/client'

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  icon: ReactNode
  color: string
}

function StatCard({ label, value, sub, icon, color }: StatCardProps) {
  return (
    <div className="card p-5 flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
        {icon}
      </div>
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        <p className="text-2xl font-bold text-slate-900">{value}</p>
        {sub && <p className="text-xs text-slate-400">{sub}</p>}
      </div>
    </div>
  )
}

export default function StatsOverview() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      setStats(await api.getStats())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="text-center py-12 text-slate-400">Loading stats…</div>
  if (!stats) return null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">AP Invoice Processing Overview</p>
        </div>
        <button onClick={load} className="btn-secondary">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Concept overview */}
      <div className="card p-5 bg-gradient-to-r from-blue-600 to-blue-700 text-white border-0">
        <h2 className="font-semibold text-lg mb-2">OpenAI Agents SDK — 4 Core Primitives</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          {[
            { name: 'Agents', desc: '5 specialized agents, each focused on one task' },
            { name: 'Handoffs', desc: 'Triage → Extract → Vendor → PO → Decision' },
            { name: 'Tools', desc: 'llmwhisperer_extract, vendor_lookup, po_lookup, approve/flag' },
            { name: 'Guardrails', desc: 'PDF validation (input) + decision fields (output)' },
          ].map((p) => (
            <div key={p.name} className="bg-white/10 rounded-lg p-3">
              <p className="font-semibold">{p.name}</p>
              <p className="text-blue-100 text-xs mt-1">{p.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Processed"
          value={stats.total_processed}
          icon={<FileText className="w-6 h-6 text-blue-600" />}
          color="bg-blue-100"
        />
        <StatCard
          label="Auto-Approved"
          value={stats.approved}
          sub={`${stats.approval_rate}% approval rate`}
          icon={<CheckCircle2 className="w-6 h-6 text-emerald-600" />}
          color="bg-emerald-100"
        />
        <StatCard
          label="Flagged for Review"
          value={stats.flagged_for_review}
          icon={<AlertTriangle className="w-6 h-6 text-amber-600" />}
          color="bg-amber-100"
        />
        <StatCard
          label="Avg Confidence"
          value={`${Math.round(stats.avg_confidence_score * 100)}%`}
          icon={<TrendingUp className="w-6 h-6 text-purple-600" />}
          color="bg-purple-100"
        />
      </div>

      {/* Common flag reasons */}
      {stats.common_flag_reasons.length > 0 && (
        <div className="card p-5">
          <h3 className="font-semibold text-slate-900 mb-4">Common Flag Reasons</h3>
          <div className="space-y-2">
            {stats.common_flag_reasons.map((r, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-700 truncate">{r.reason || '(no reason)'}</p>
                </div>
                <span className="text-xs font-medium text-slate-500 flex-shrink-0">{r.count}</span>
                <div className="w-24 h-1.5 bg-slate-100 rounded-full overflow-hidden flex-shrink-0">
                  <div
                    className="h-full bg-amber-400 rounded-full"
                    style={{ width: `${(r.count / (stats.flagged_for_review || 1)) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pipeline flow diagram */}
      <div className="card p-5">
        <h3 className="font-semibold text-slate-900 mb-4">Pipeline Architecture</h3>
        <div className="overflow-x-auto">
          <div className="flex items-start gap-2 min-w-max">
            {[
              { name: 'Triage', desc: 'Route & validate', color: 'border-blue-300 bg-blue-50' },
              { name: 'Extraction', desc: 'OCR + parse fields', color: 'border-indigo-300 bg-indigo-50' },
              { name: 'Vendor Lookup', desc: 'Validate vendor', color: 'border-violet-300 bg-violet-50' },
              { name: 'PO Match', desc: '3-way match', color: 'border-purple-300 bg-purple-50' },
              { name: 'Decision', desc: 'Approve or flag', color: 'border-pink-300 bg-pink-50' },
            ].map((step, i, arr) => (
              <Fragment key={step.name}>
                <div className={`border-2 rounded-xl p-3 text-center w-28 ${step.color}`}>
                  <p className="text-sm font-semibold text-slate-800">{step.name}</p>
                  <p className="text-xs text-slate-500 mt-1">{step.desc}</p>
                </div>
                {i < arr.length - 1 && (
                  <div className="flex items-center self-center text-slate-300 text-lg font-bold">→</div>
                )}
              </Fragment>
            ))}
          </div>
          <div className="mt-4 flex gap-6 text-xs text-slate-500">
            <span>📎 Tools: llmwhisperer_extract, vendor_lookup, po_lookup, approve_invoice, flag_for_review</span>
            <span>🛡 Guardrails: PDF check (input) + decision fields (output)</span>
          </div>
        </div>
      </div>
    </div>
  )
}

import { type ReactNode, useEffect, useState } from 'react'
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
          <h1 className="text-2xl font-semibold text-slate-900">Stats Overview</h1>
          <p className="text-sm text-slate-500 mt-1">AP Invoice Processing Summary</p>
        </div>
        <button onClick={load} className="btn-secondary">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

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
    </div>
  )
}

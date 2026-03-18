import { useEffect, useState } from 'react'
import { Activity, ExternalLink, RefreshCw, AlertCircle } from 'lucide-react'

interface LangfuseTrace {
  id: string
  name: string
  timestamp: string
  latency?: number
  observations?: number
  status?: string
}

interface LogsResponse {
  available: boolean
  traces: LangfuseTrace[]
  langfuse_url: string
}

function formatName(name: string): string {
  // Extract filename from "Process this invoice PDF located at: /uploads/abc_file.pdf"
  const match = name.match(/located at:.*?([^/\\]+\.pdf)/i)
  if (match) return `📄 ${match[1]}`
  if (name.toLowerCase().includes('process this invoice')) return '📄 Invoice Processing'
  if (name.length > 60) return name.slice(0, 60) + '…'
  return name
}

function formatDuration(ms?: number): string {
  if (!ms) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatTime(ts: string): string {
  const d = new Date(ts)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function Logs() {
  const [data, setData] = useState<LogsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    setError('')
    fetch('/api/logs')
      .then(r => r.json())
      .then(setData)
      .catch(() => setError('Failed to load logs'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Pipeline Logs</h1>
          <p className="text-sm text-slate-500 mt-0.5">Recent agent runs via Langfuse</p>
        </div>
        <div className="flex items-center gap-3">
          {data?.langfuse_url && (
            <a
              href={data.langfuse_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Open Langfuse
            </a>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-white border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 disabled:opacity-40"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {!data?.available && !loading && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">Langfuse not configured</p>
            <p className="mt-1 text-amber-700">Add <code className="bg-amber-100 px-1 rounded">LANGFUSE_PUBLIC_KEY</code>, <code className="bg-amber-100 px-1 rounded">LANGFUSE_SECRET_KEY</code>, and <code className="bg-amber-100 px-1 rounded">LANGFUSE_BASE_URL</code> to your <code className="bg-amber-100 px-1 rounded">.env</code> file and restart the server.</p>
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">{error}</div>
      )}

      {loading && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {!loading && data?.available && data.traces.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-slate-400">
          <Activity className="w-10 h-10 mb-3 opacity-30" />
          <p className="text-sm">No traces yet — process an invoice to see logs here.</p>
        </div>
      )}

      {!loading && data?.available && data.traces.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Run</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Time</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Duration</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Observations</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.traces.map((trace) => (
                <tr key={trace.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 text-slate-700 max-w-xs">
                    <span className="truncate block">{formatName(trace.name)}</span>
                    <span className="text-xs text-slate-400 font-mono">{trace.id.slice(0, 8)}…</span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 whitespace-nowrap">{formatTime(trace.timestamp)}</td>
                  <td className="px-4 py-3 text-slate-500 whitespace-nowrap">{formatDuration(trace.latency)}</td>
                  <td className="px-4 py-3 text-slate-500">{trace.observations ?? '—'}</td>
                  <td className="px-4 py-3 text-right">
                    {data.langfuse_url && (
                      <a
                        href={`${data.langfuse_url}/trace/${trace.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-blue-500 hover:text-blue-700"
                      >
                        <ExternalLink className="w-3 h-3" />
                        View
                      </a>
                    )}
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

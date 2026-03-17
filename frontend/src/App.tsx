import { useState, useEffect } from 'react'
import { LayoutDashboard, FileText, AlertTriangle, Building2, Menu, Bot, Info } from 'lucide-react'
import clsx from 'clsx'
import Dashboard from './components/Dashboard'
import About from './components/About'
import InvoiceList from './components/InvoiceList'
import ReviewQueue from './components/ReviewQueue'
import VendorsAndPOs from './components/VendorsAndPOs'
import { api, type Stats } from './api/client'

type Page = 'dashboard' | 'invoices' | 'review' | 'reference' | 'about'

const NAV = [
  { id: 'dashboard', label: 'Dashboard',    icon: LayoutDashboard },
  { id: 'invoices',  label: 'Invoices',     icon: FileText },
  { id: 'review',    label: 'Review Queue', icon: AlertTriangle },
  { id: 'reference', label: 'Vendors & POs', icon: Building2 },
  { id: 'about',     label: 'About',        icon: Info },
] as const

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    api.getStats().then(setStats).catch(() => {})
  }, [page])

  const navigate = (p: Page) => {
    setPage(p)
    setSidebarOpen(false)
  }

  return (
    <div className="min-h-screen flex">
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside className={clsx(
        'fixed inset-y-0 left-0 z-30 w-64 bg-slate-900 flex flex-col transition-transform duration-200',
        'lg:static lg:translate-x-0',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        <div className="flex items-center gap-3 px-5 py-5 border-b border-slate-700/50">
          <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center flex-shrink-0">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="font-semibold text-white text-sm leading-tight">AP Invoice Agent</p>
            <p className="text-xs text-slate-400">OpenAI Agents SDK</p>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => navigate(id)}
              className={clsx(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                page === id
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </button>
          ))}
        </nav>

        <div className="px-4 py-4 border-t border-slate-700/50">
          {stats ? (
            <div className="bg-slate-800 rounded-lg p-3 text-xs text-slate-400 space-y-2">
              <p className="font-semibold text-slate-300 text-xs uppercase tracking-wide">Pipeline Stats</p>
              <div className="flex justify-between">
                <span>Processed</span>
                <span className="text-slate-200 font-medium">{stats.total_processed}</span>
              </div>
              <div className="flex justify-between">
                <span>Approved</span>
                <span className="text-emerald-400 font-medium">{stats.approved}</span>
              </div>
              <div className="flex justify-between">
                <span>Pending review</span>
                <span className="text-amber-400 font-medium">{stats.flagged_for_review}</span>
              </div>
              <div className="flex justify-between">
                <span>Approval rate</span>
                <span className="text-blue-400 font-medium">{stats.approval_rate}%</span>
              </div>
            </div>
          ) : (
            <div className="bg-slate-800 rounded-lg p-3 text-xs text-slate-500 text-center">
              Loading stats…
            </div>
          )}
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 bg-white border-b border-slate-200">
          <button onClick={() => setSidebarOpen(true)} className="p-1 text-slate-500">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-blue-600" />
            <span className="font-semibold text-slate-900 text-sm">AP Invoice Agent</span>
          </div>
        </header>

        <main className="flex-1 overflow-auto">
          <div className={clsx('p-6',                    page !== 'dashboard' && 'hidden')}><Dashboard /></div>
          <div className={clsx('max-w-4xl mx-auto p-6', page !== 'invoices'  && 'hidden')}><InvoiceList /></div>
          <div className={clsx('max-w-4xl mx-auto p-6', page !== 'review'    && 'hidden')}><ReviewQueue /></div>
          <div className={clsx('max-w-4xl mx-auto p-6', page !== 'reference' && 'hidden')}><VendorsAndPOs /></div>
          <div className={clsx('max-w-4xl mx-auto p-6', page !== 'about'     && 'hidden')}><About /></div>
        </main>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { LayoutDashboard, Upload, FileText, AlertTriangle, Building2, Menu, Bot } from 'lucide-react'
import clsx from 'clsx'
import StatsOverview from './components/StatsOverview'
import InvoiceUpload from './components/InvoiceUpload'
import InvoiceList from './components/InvoiceList'
import ReviewQueue from './components/ReviewQueue'
import VendorsAndPOs from './components/VendorsAndPOs'

type Page = 'dashboard' | 'upload' | 'invoices' | 'review' | 'reference'

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'upload',    label: 'Process Invoice', icon: Upload },
  { id: 'invoices',  label: 'Invoices', icon: FileText },
  { id: 'review',    label: 'Review Queue', icon: AlertTriangle },
  { id: 'reference', label: 'Vendors & POs', icon: Building2 },
] as const

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const navigate = (p: Page) => {
    setPage(p)
    setSidebarOpen(false)
  }

  return (
    <div className="min-h-screen flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={clsx(
        'fixed inset-y-0 left-0 z-30 w-64 bg-slate-900 flex flex-col transition-transform duration-200',
        'lg:static lg:translate-x-0',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-slate-700/50">
          <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center flex-shrink-0">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="font-semibold text-white text-sm leading-tight">AP Invoice Agent</p>
            <p className="text-xs text-slate-400">OpenAI Agents SDK</p>
          </div>
        </div>

        {/* Nav */}
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

        {/* SDK badge */}
        <div className="px-4 py-4 border-t border-slate-700/50">
          <div className="bg-slate-800 rounded-lg p-3 text-xs text-slate-400 space-y-1">
            <p className="font-semibold text-slate-300">Agents SDK Primitives</p>
            <p>🤖 5 Specialized Agents</p>
            <p>🔀 Chain Handoffs</p>
            <p>🔧 5 @function_tools</p>
            <p>🛡 Input + Output Guardrails</p>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar (mobile) */}
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 bg-white border-b border-slate-200">
          <button onClick={() => setSidebarOpen(true)} className="p-1 text-slate-500">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-blue-600" />
            <span className="font-semibold text-slate-900 text-sm">AP Invoice Agent</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 overflow-auto">
          <div className="max-w-4xl mx-auto">
            {page === 'dashboard' && <StatsOverview />}
            {page === 'upload'    && <InvoiceUpload onProcessingComplete={() => {}} />}
            {page === 'invoices'  && <InvoiceList />}
            {page === 'review'    && <ReviewQueue />}
            {page === 'reference' && <VendorsAndPOs />}
          </div>
        </main>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Building2, FileText, RefreshCw } from 'lucide-react'
import { api, Vendor, PurchaseOrder } from '../api/client'
import clsx from 'clsx'

function VendorStatusBadge({ status }: { status: Vendor['status'] }) {
  if (status === 'active') return <span className="badge-green">Active</span>
  if (status === 'blocked') return <span className="badge-red">Blocked</span>
  return <span className="badge-gray">Inactive</span>
}

function POStatusBadge({ status }: { status: PurchaseOrder['status'] }) {
  if (status === 'open') return <span className="badge-blue">Open</span>
  if (status === 'partially_received') return <span className="badge-yellow">Partial</span>
  return <span className="badge-gray">Closed</span>
}

export default function VendorsAndPOs() {
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [pos, setPOs] = useState<PurchaseOrder[]>([])
  const [activeTab, setActiveTab] = useState<'vendors' | 'pos'>('vendors')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [v, p] = await Promise.all([api.getVendors(), api.getPurchaseOrders()])
      setVendors(v)
      setPOs(p)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Reference Data</h1>
          <p className="text-sm text-slate-500 mt-1">Vendor master & purchase orders used by agents</p>
        </div>
        <button onClick={load} className="btn-secondary">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-200">
        {(['vendors', 'pos'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-4 py-2.5 text-sm font-medium -mb-px transition-colors flex items-center gap-2',
              activeTab === tab
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-700'
            )}
          >
            {tab === 'vendors' ? <Building2 className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
            {tab === 'vendors' ? `Vendors (${vendors.length})` : `Purchase Orders (${pos.length})`}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading…</div>
      ) : activeTab === 'vendors' ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">ID</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Vendor Name</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Tax ID</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Payment Terms</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {vendors.map((v) => (
                  <tr key={v.vendor_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">{v.vendor_id}</td>
                    <td className="px-4 py-3 font-medium text-slate-900">{v.vendor_name}</td>
                    <td className="px-4 py-3 text-slate-500">{v.tax_id || '—'}</td>
                    <td className="px-4 py-3 text-slate-600">{v.payment_terms}</td>
                    <td className="px-4 py-3"><VendorStatusBadge status={v.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">PO Number</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Vendor</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Department</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Amount</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Date</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {pos.map((po) => (
                  <tr key={po.po_number} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs font-medium text-blue-700">{po.po_number}</td>
                    <td className="px-4 py-3 text-slate-600">{po.vendor_id}</td>
                    <td className="px-4 py-3 text-slate-500">{po.department || '—'}</td>
                    <td className="px-4 py-3 text-right font-medium text-slate-900">
                      ${po.total_amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{po.po_date || '—'}</td>
                    <td className="px-4 py-3"><POStatusBadge status={po.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

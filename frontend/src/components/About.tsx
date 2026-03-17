import { Fragment } from 'react'

export default function About() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">About</h1>
        <p className="text-sm text-slate-500 mt-1">OpenAI Agents SDK — How this app is built</p>
      </div>

      {/* 4 Core Primitives */}
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

      {/* Pipeline Architecture */}
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
          <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
            <span>📎 Tools: llmwhisperer_extract, vendor_lookup, po_lookup, duplicate_invoice_check, content_fingerprint_check, invoice_fraud_analysis, vendor_history_context, approve_invoice, flag_for_review</span>
            <span>🛡 Guardrails: PDF check (input) + decision fields (output)</span>
          </div>
        </div>
      </div>

      {/* Agent descriptions */}
      <div className="card p-5">
        <h3 className="font-semibold text-slate-900 mb-4">Agent Responsibilities</h3>
        <div className="space-y-3">
          {[
            {
              agent: 'Triage Agent',
              role: 'Entry point & router',
              detail: 'Routes invoice processing requests to the Extraction Agent. Answers status queries (pending invoices, stats, vendor history) directly using the invoice_query tool without spinning up the full pipeline.',
              color: 'bg-blue-50 border-blue-200',
            },
            {
              agent: 'Extraction Agent',
              role: 'OCR + field parsing',
              detail: 'Calls LLMWhisperer to OCR the PDF. Verifies the document is actually an invoice. Checks for exact duplicate invoice numbers immediately after extraction. Extracts all structured fields and assigns a confidence score.',
              color: 'bg-indigo-50 border-indigo-200',
            },
            {
              agent: 'Vendor Lookup Agent',
              role: 'Vendor validation',
              detail: 'Searches the vendor master for the invoice vendor by name and tax ID. Validates vendor status (active/inactive). Resolves vendor_id for downstream agents.',
              color: 'bg-violet-50 border-violet-200',
            },
            {
              agent: 'PO Matching Agent',
              role: '3-way match',
              detail: 'Matches the invoice to a purchase order. Computes variance between invoice amount and PO amount. Classifies match as exact_match, within_tolerance, amount_mismatch, over_tolerance, or no_po_referenced.',
              color: 'bg-purple-50 border-purple-200',
            },
            {
              agent: 'Decision Agent',
              role: 'Final decision + fraud analysis',
              detail: 'Runs content fingerprint check (AI-manipulated resubmission detection), behavioral fraud analysis (velocity, invoice splitting, threshold-avoidance), and vendor history context. Makes the final approve or flag decision.',
              color: 'bg-pink-50 border-pink-200',
            },
          ].map((a) => (
            <div key={a.agent} className={`border rounded-lg p-4 ${a.color}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className="font-semibold text-slate-800 text-sm">{a.agent}</span>
                <span className="text-xs text-slate-500">— {a.role}</span>
              </div>
              <p className="text-xs text-slate-600">{a.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

import React, { useState } from 'react'
import { CheckCircle2, Circle, Loader2, XCircle, ChevronDown, ChevronUp, ArrowRight, Wrench } from 'lucide-react'
import { TimelineStep } from './InvoiceUpload'
import { SSEEvent } from '../api/client'
import clsx from 'clsx'

interface Props {
  steps: TimelineStep[]
  isProcessing: boolean
}

const AGENT_DESCRIPTIONS: Record<string, string> = {
  'Triage Agent': 'Validates the invoice and kicks off the pipeline',
  'Extraction Agent': 'OCRs the PDF and parses invoice fields',
  'Vendor Lookup Agent': 'Validates vendor against master database',
  'PO Matching Agent': 'Matches invoice against purchase orders',
  'Decision Agent': 'Makes final approval or flag decision',
}

function StatusIcon({ status }: { status: TimelineStep['status'] }) {
  if (status === 'done') return <CheckCircle2 className="w-6 h-6 text-emerald-500 flex-shrink-0" />
  if (status === 'running') return (
    <div className="relative flex-shrink-0">
      <div className="w-6 h-6 rounded-full bg-blue-100 border-2 border-blue-500 pulse-ring absolute inset-0" />
      <Loader2 className="w-6 h-6 text-blue-500 animate-spin relative" />
    </div>
  )
  if (status === 'error') return <XCircle className="w-6 h-6 text-red-500 flex-shrink-0" />
  return <Circle className="w-6 h-6 text-slate-300 flex-shrink-0" />
}

function EventRow({ event }: { event: SSEEvent }) {
  if (event.event === 'tool_call') {
    return (
      <div className="flex items-start gap-2 text-xs">
        <Wrench className="w-3.5 h-3.5 text-blue-400 flex-shrink-0 mt-0.5" />
        <div>
          <span className="font-medium text-blue-700">Tool call: </span>
          <span className="text-slate-700">{event.tool}</span>
          {event.input && (
            <div className="mt-1 text-slate-500 font-mono bg-slate-50 rounded p-1 overflow-hidden text-ellipsis whitespace-nowrap max-w-xs">
              {JSON.stringify(event.input).slice(0, 120)}
            </div>
          )}
        </div>
      </div>
    )
  }
  if (event.event === 'tool_result') {
    return (
      <div className="flex items-start gap-2 text-xs">
        <span className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-emerald-400">↩</span>
        <div className="text-slate-600 font-mono bg-emerald-50 rounded p-1 overflow-hidden text-ellipsis whitespace-nowrap max-w-xs">
          {String(event.output).slice(0, 150)}
        </div>
      </div>
    )
  }
  if (event.event === 'agent_message') {
    return (
      <div className="text-xs text-slate-600 bg-slate-50 rounded p-1.5 max-w-sm whitespace-pre-wrap break-words max-h-20 overflow-auto">
        {event.message.slice(0, 300)}
      </div>
    )
  }
  return null
}

export default function ProcessingTimeline({ steps, isProcessing }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const toggle = (agent: string) =>
    setExpanded((prev) => ({ ...prev, [agent]: !prev[agent] }))

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-5">
        <h3 className="font-semibold text-slate-900">Agent Pipeline</h3>
        {isProcessing && (
          <span className="text-xs text-blue-600 font-medium flex items-center gap-1.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Processing…
          </span>
        )}
      </div>

      {/* Horizontal step indicators */}
      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-1">
        {steps.map((step, i) => (
          <React.Fragment key={step.agent}>
            <div className="flex flex-col items-center gap-1 min-w-[90px]">
              <StatusIcon status={step.status} />
              <span className={clsx(
                'text-xs text-center leading-tight',
                step.status === 'running' && 'text-blue-600 font-medium',
                step.status === 'done' && 'text-emerald-600',
                step.status === 'error' && 'text-red-600',
                step.status === 'pending' && 'text-slate-400',
              )}>
                {step.agent.replace(' Agent', '')}
              </span>
            </div>
            {i < steps.length - 1 && (
              <ArrowRight className={clsx(
                'w-4 h-4 flex-shrink-0',
                steps[i + 1].status !== 'pending' ? 'text-blue-400' : 'text-slate-200'
              )} />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Detailed step list */}
      <div className="space-y-3">
        {steps.map((step) => (
          <div
            key={step.agent}
            className={clsx(
              'rounded-lg border transition-colors',
              step.status === 'running' && 'border-blue-200 bg-blue-50/50',
              step.status === 'done' && 'border-emerald-100 bg-emerald-50/30',
              step.status === 'error' && 'border-red-200 bg-red-50/30',
              step.status === 'pending' && 'border-slate-100 bg-slate-50/50',
            )}
          >
            <button
              className="w-full flex items-center gap-3 p-3 text-left"
              onClick={() => step.events.length > 0 && toggle(step.agent)}
              disabled={step.events.length === 0}
            >
              <StatusIcon status={step.status} />
              <div className="flex-1 min-w-0">
                <p className={clsx(
                  'font-medium text-sm',
                  step.status === 'running' ? 'text-blue-800' :
                  step.status === 'done' ? 'text-emerald-800' :
                  step.status === 'error' ? 'text-red-800' : 'text-slate-500'
                )}>
                  {step.agent}
                </p>
                <p className="text-xs text-slate-500 truncate">
                  {AGENT_DESCRIPTIONS[step.agent]}
                </p>
              </div>
              {step.events.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-slate-400">{step.events.length} events</span>
                  {expanded[step.agent]
                    ? <ChevronUp className="w-4 h-4 text-slate-400" />
                    : <ChevronDown className="w-4 h-4 text-slate-400" />
                  }
                </div>
              )}
            </button>

            {expanded[step.agent] && step.events.length > 0 && (
              <div className="px-3 pb-3 space-y-2 border-t border-slate-100 pt-2 ml-9">
                {step.events.map((e, i) => (
                  <EventRow key={i} event={e} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

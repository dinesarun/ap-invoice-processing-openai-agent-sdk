import { useCallback, useState, useRef } from 'react'
import { Upload, FileText, X } from 'lucide-react'
import { api, SSEEvent } from '../api/client'
import ProcessingTimeline from './ProcessingTimeline'
import clsx from 'clsx'

interface Props {
  onProcessingComplete: () => void
}

const PIPELINE_AGENTS = [
  'Triage Agent',
  'Extraction Agent',
  'Vendor Lookup Agent',
  'PO Matching Agent',
  'Decision Agent',
]

export interface TimelineStep {
  agent: string
  status: 'pending' | 'running' | 'done' | 'error'
  events: SSEEvent[]
  message?: string
}

export default function InvoiceUpload({ onProcessingComplete }: Props) {
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [steps, setSteps] = useState<TimelineStep[]>([])
  const [finalOutput, setFinalOutput] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const initSteps = (): TimelineStep[] =>
    PIPELINE_AGENTS.map((agent) => ({ agent, status: 'pending', events: [] }))

  const handleFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a PDF file.')
      return
    }
    setSelectedFile(file)
    setError(null)
    setFinalOutput(null)
    setSteps([])
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [])

  const handleProcess = () => {
    if (!selectedFile) return
    setIsProcessing(true)
    setError(null)
    setFinalOutput(null)

    const initial = initSteps()
    initial[0].status = 'running'
    setSteps(initial)

    api.uploadInvoiceStream(
      selectedFile,
      (event) => {
        setSteps((prev) => {
          const next = [...prev]

          if (event.event === 'upload_complete') {
            return next
          }

          if (event.event === 'handoff') {
            // Mark from_agent as done, mark to_agent as running
            const fromIdx = next.findIndex((s) => s.agent === event.from_agent)
            const toIdx = next.findIndex((s) => s.agent === event.to_agent)
            if (fromIdx !== -1) next[fromIdx] = { ...next[fromIdx], status: 'done' }
            if (toIdx !== -1) next[toIdx] = { ...next[toIdx], status: 'running', events: [...next[toIdx].events, event] }
            return next
          }

          if (event.event === 'tool_call' || event.event === 'tool_result' || event.event === 'agent_message') {
            const agentName = (event as { agent?: string }).agent
            const idx = next.findIndex((s) => s.agent === agentName)
            if (idx !== -1) {
              next[idx] = { ...next[idx], events: [...next[idx].events, event] }
            }
            return next
          }

          if (event.event === 'pipeline_complete') {
            // Mark all running steps as done
            return next.map((s) => s.status === 'running' ? { ...s, status: 'done' } : s)
          }

          if (event.event === 'pipeline_error') {
            return next.map((s) => s.status === 'running' ? { ...s, status: 'error' } : s)
          }

          return next
        })

        if (event.event === 'pipeline_complete') {
          setFinalOutput(event.final_output)
        }
        if (event.event === 'pipeline_error') {
          setError(event.message)
        }
      },
      () => {
        setIsProcessing(false)
        onProcessingComplete()
      },
      (err) => {
        setError(err)
        setIsProcessing(false)
      }
    )
  }

  const reset = () => {
    setSelectedFile(null)
    setSteps([])
    setFinalOutput(null)
    setError(null)
    setIsProcessing(false)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Process Invoice</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload a PDF invoice to start the agentic processing pipeline.
        </p>
      </div>

      {/* Upload zone */}
      <div className="card p-6">
        <div
          className={clsx(
            'border-2 border-dashed rounded-xl p-12 text-center transition-colors cursor-pointer',
            isDragging
              ? 'border-blue-500 bg-blue-50'
              : selectedFile
              ? 'border-emerald-400 bg-emerald-50'
              : 'border-slate-200 hover:border-blue-400 hover:bg-blue-50/50'
          )}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => !selectedFile && fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />

          {selectedFile ? (
            <div className="space-y-3">
              <div className="flex items-center justify-center gap-3">
                <FileText className="w-8 h-8 text-emerald-500" />
                <div className="text-left">
                  <p className="font-medium text-slate-900">{selectedFile.name}</p>
                  <p className="text-sm text-slate-500">{(selectedFile.size / 1024).toFixed(1)} KB</p>
                </div>
                {!isProcessing && (
                  <button
                    onClick={(e) => { e.stopPropagation(); reset() }}
                    className="p-1 rounded-full hover:bg-slate-200 text-slate-400 hover:text-slate-600 transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
              {!isProcessing && (
                <button onClick={(e) => { e.stopPropagation(); handleProcess() }} className="btn-primary">
                  <Upload className="w-4 h-4" />
                  Process Invoice
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <Upload className="w-10 h-10 text-slate-300 mx-auto" />
              <div>
                <p className="font-medium text-slate-700">Drop a PDF invoice here</p>
                <p className="text-sm text-slate-400 mt-1">or click to browse</p>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}
      </div>

      {/* Processing timeline */}
      {steps.length > 0 && (
        <ProcessingTimeline steps={steps} isProcessing={isProcessing} />
      )}

      {/* Final output */}
      {finalOutput && (
        <div className="card p-6">
          <h3 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
            Pipeline Complete — Agent Response
          </h3>
          <pre className="text-sm text-slate-700 bg-slate-50 rounded-lg p-4 overflow-auto whitespace-pre-wrap max-h-64">
            {finalOutput}
          </pre>
          <div className="mt-4 flex gap-3">
            <button onClick={reset} className="btn-secondary">Process Another</button>
          </div>
        </div>
      )}
    </div>
  )
}

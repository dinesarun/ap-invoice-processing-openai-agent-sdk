import { useEffect, useRef, useState } from 'react'
import { Send, Paperclip, Bot, User, ChevronDown, ChevronUp, Loader2, X } from 'lucide-react'
import { api, type SSEEvent } from '../api/client'

// ─── Types ────────────────────────────────────────────────────────────────────

type AgentStep = {
  type: string
  description: string
}

type ChatMsg = {
  id: string
  role: 'user' | 'agent'
  text: string
  steps: AgentStep[]
  isLoading: boolean
  error?: string
}

// ─── Quick actions ─────────────────────────────────────────────────────────

const QUICK_ACTIONS = [
  { label: 'Process Invoice',    icon: '📄', action: 'upload'  as const },
  { label: 'Pending Reviews',    icon: '⏳', message: 'Show all pending invoices in the review queue' },
  { label: 'Recent Approvals',   icon: '✅', message: 'Show recently approved invoices' },
  { label: 'Flagged Items',      icon: '🚩', message: 'Show flagged invoices' },
  { label: 'Processing Stats',   icon: '📊', message: 'Show overall processing statistics' },
  { label: 'All Invoices',       icon: '📋', message: 'Show all recent invoices' },
]

// ─── SSE reader helper ────────────────────────────────────────────────────

function readSSEStream(
  fetchPromise: Promise<Response>,
  onEvent: (e: SSEEvent) => void,
  onDone: () => void,
  onError: (msg: string) => void,
) {
  fetchPromise
    .then(async (res) => {
      if (!res.ok) throw new Error(`Request failed: ${res.statusText}`)
      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6)) as SSEEvent
              onEvent(data)
              if (data.event === 'pipeline_complete' || data.event === 'pipeline_error') {
                onDone()
              }
            } catch { /* skip */ }
          }
        }
      }
      onDone()
    })
    .catch((e) => onError(String(e)))
}

// ─── Step label helper ────────────────────────────────────────────────────

function stepLabel(e: SSEEvent): string | null {
  if (e.event === 'handoff') return `↪ ${e.from_agent} → ${e.to_agent}`
  if (e.event === 'tool_call') return `🔧 ${e.agent}: ${e.tool}`
  if (e.event === 'tool_result') return `✓ Result received`
  return null
}

// ─── Message bubble ───────────────────────────────────────────────────────

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="flex items-end gap-2 max-w-[80%]">
        <div className="bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm leading-relaxed">
          {text}
        </div>
        <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0 mb-0.5">
          <User className="w-3.5 h-3.5 text-slate-600" />
        </div>
      </div>
    </div>
  )
}

function AgentBubble({ msg }: { msg: ChatMsg }) {
  const [stepsOpen, setStepsOpen] = useState(false)

  return (
    <div className="flex justify-start">
      <div className="flex items-end gap-2 max-w-[85%]">
        <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mb-0.5">
          <Bot className="w-3.5 h-3.5 text-white" />
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm px-4 py-3 text-sm shadow-sm space-y-2 min-w-[120px]">
          {msg.isLoading && !msg.text ? (
            <div className="flex items-center gap-2 text-slate-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span className="text-xs">
                {msg.steps.length > 0 ? msg.steps[msg.steps.length - 1].description : 'Thinking…'}
              </span>
            </div>
          ) : (
            <>
              <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">{msg.text || msg.error}</p>
              {msg.steps.length > 0 && (
                <div>
                  <button
                    onClick={() => setStepsOpen(!stepsOpen)}
                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors"
                  >
                    {stepsOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    {stepsOpen ? 'Hide' : 'Show'} agent steps ({msg.steps.length})
                  </button>
                  {stepsOpen && (
                    <div className="mt-2 space-y-1 border-t border-slate-100 pt-2">
                      {msg.steps.map((s, i) => (
                        <p key={i} className="text-xs text-slate-400">{s.description}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <div className={`flex items-center gap-1 pt-1 text-xs ${msg.error ? 'text-red-400' : 'text-emerald-500'}`}>
                {msg.error ? (
                  <><span>✗</span><span>Failed</span></>
                ) : (
                  <><span>✓</span><span>Completed</span></>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────

const STORAGE_KEY = 'ap_dashboard_messages'

function loadMessages(): ChatMsg[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as ChatMsg[]
    // Drop any messages that were mid-flight when the page was closed
    return parsed.filter((m) => !m.isLoading)
  } catch {
    return []
  }
}

export default function Dashboard() {
  const [messages, setMessages] = useState<ChatMsg[]>(loadMessages)
  const [input, setInput] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [submitterNotes, setSubmitterNotes] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const notesRef = useRef<HTMLTextAreaElement>(null)

  // Persist completed messages to localStorage
  useEffect(() => {
    const completed = messages.filter((m) => !m.isLoading)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(completed))
  }, [messages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Append a step to the last agent message
  const appendStep = (step: AgentStep) => {
    setMessages((prev) => {
      const msgs = [...prev]
      const last = msgs[msgs.length - 1]
      if (last?.role === 'agent') {
        return [...msgs.slice(0, -1), { ...last, steps: [...last.steps, step] }]
      }
      return msgs
    })
  }

  // Set final text on the last agent message
  const finalizeAgent = (text: string, error?: string) => {
    setMessages((prev) => {
      const msgs = [...prev]
      const last = msgs[msgs.length - 1]
      if (last?.role === 'agent') {
        return [...msgs.slice(0, -1), { ...last, text, error, isLoading: false }]
      }
      return msgs
    })
    setIsProcessing(false)
  }

  const handleSSEEvent = (e: SSEEvent) => {
    const label = stepLabel(e)
    if (label) appendStep({ type: e.event, description: label })

    if (e.event === 'agent_message') {
      setMessages((prev) => {
        const msgs = [...prev]
        const last = msgs[msgs.length - 1]
        if (last?.role === 'agent') {
          return [...msgs.slice(0, -1), { ...last, text: e.message }]
        }
        return msgs
      })
    }

    if (e.event === 'pipeline_complete') {
      finalizeAgent(e.final_output || '')
    }

    if (e.event === 'pipeline_error') {
      finalizeAgent('', e.message || 'An error occurred')
    }
  }

  const startAgentMessage = (): ChatMsg => ({
    id: crypto.randomUUID(),
    role: 'agent',
    text: '',
    steps: [],
    isLoading: true,
  })

  const sendTextMessage = (text: string) => {
    if (!text.trim() || isProcessing) return
    setIsProcessing(true)
    setInput('')

    const userMsg: ChatMsg = { id: crypto.randomUUID(), role: 'user', text, steps: [], isLoading: false }
    const agentMsg = startAgentMessage()
    setMessages((prev) => [...prev, userMsg, agentMsg])

    readSSEStream(
      fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      }),
      handleSSEEvent,
      () => setIsProcessing(false),
      (err) => finalizeAgent('', err),
    )
  }

  const handleFileUpload = (file: File, notes: string) => {
    if (!file || isProcessing) return
    setIsProcessing(true)
    setPendingFile(null)
    setSubmitterNotes('')

    const notesSummary = notes.trim() ? ` — "${notes.trim()}"` : ''
    const userMsg: ChatMsg = {
      id: crypto.randomUUID(),
      role: 'user',
      text: `📄 Processing: ${file.name}${notesSummary}`,
      steps: [],
      isLoading: false,
    }
    const agentMsg = startAgentMessage()
    setMessages((prev) => [...prev, userMsg, agentMsg])

    const formData = new FormData()
    formData.append('file', file)
    if (notes.trim()) formData.append('notes', notes.trim())

    readSSEStream(
      fetch('/api/upload-invoice', { method: 'POST', body: formData }),
      handleSSEEvent,
      () => setIsProcessing(false),
      (err) => finalizeAgent('', err),
    )
  }

  const handleFileSelected = (file: File) => {
    if (!file || isProcessing) return
    setPendingFile(file)
    setSubmitterNotes('')
    // Focus the notes field after render
    setTimeout(() => notesRef.current?.focus(), 50)
  }

  const cancelPendingUpload = () => {
    setPendingFile(null)
    setSubmitterNotes('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleQuickAction = (action: typeof QUICK_ACTIONS[0]) => {
    if (action.action === 'upload') {
      fileInputRef.current?.click()
    } else if ('message' in action) {
      sendTextMessage(action.message)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendTextMessage(input)
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] max-w-4xl mx-auto">
      {isProcessing && (
        <div className="flex items-center gap-2 px-4 py-2 bg-blue-50 border border-blue-100 rounded-xl mb-3 text-sm text-blue-700">
          <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-500"></span>
          </span>
          <span className="font-medium">Processing</span>
          <span className="text-blue-500">·</span>
          <span className="text-blue-600 truncate">
            {messages.filter(m => m.role === 'agent' && m.isLoading).slice(-1)[0]?.steps.slice(-1)[0]?.description ?? 'Pipeline running…'}
          </span>
        </div>
      )}

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto space-y-4 px-1 pb-4">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3 py-12">
            <div className="w-14 h-14 bg-blue-100 rounded-2xl flex items-center justify-center">
              <Bot className="w-7 h-7 text-blue-600" />
            </div>
            <div>
              <p className="font-semibold text-slate-800">AP Invoice Assistant</p>
              <p className="text-sm text-slate-500 mt-1">Upload an invoice to process it, or ask me anything.</p>
            </div>
          </div>
        ) : (
          messages.map((msg) =>
            msg.role === 'user'
              ? <UserBubble key={msg.id} text={msg.text} />
              : <AgentBubble key={msg.id} msg={msg} />
          )
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick action chips */}
      <div className="flex flex-wrap gap-2 py-3">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            onClick={() => handleQuickAction(action)}
            disabled={isProcessing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 rounded-full text-slate-600 hover:bg-slate-50 hover:border-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <span>{action.icon}</span>
            {action.label}
          </button>
        ))}
      </div>

      {/* Pending file panel — shown after file selection, before upload */}
      {pendingFile && (
        <div className="bg-white border border-blue-200 rounded-xl p-4 mb-2 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-base">📄</span>
              <span className="text-sm font-medium text-slate-700 truncate">{pendingFile.name}</span>
              <span className="text-xs text-slate-400 flex-shrink-0">
                {(pendingFile.size / 1024).toFixed(0)} KB
              </span>
            </div>
            <button
              onClick={cancelPendingUpload}
              className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors flex-shrink-0 ml-2"
              title="Cancel"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <textarea
            ref={notesRef}
            value={submitterNotes}
            onChange={(e) => setSubmitterNotes(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault()
                handleFileUpload(pendingFile, submitterNotes)
              }
              if (e.key === 'Escape') cancelPendingUpload()
            }}
            placeholder="Add a note (optional) — e.g. map to PO-2024-099, pre-approved by CFO, new vendor onboarding in progress…"
            rows={2}
            className="w-full text-sm text-slate-700 placeholder:text-slate-400 border border-slate-200 rounded-lg px-3 py-2 outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100 resize-none leading-relaxed"
          />
          <div className="flex items-center justify-between mt-3">
            <p className="text-xs text-slate-400">⌘↵ to submit · Esc to cancel</p>
            <div className="flex gap-2">
              <button
                onClick={cancelPendingUpload}
                className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleFileUpload(pendingFile, submitterNotes)}
                className="px-4 py-1.5 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Process Invoice →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="bg-white border border-slate-200 rounded-xl p-3 flex items-end gap-2">
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isProcessing}
          className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-40 flex-shrink-0"
          title="Upload invoice PDF"
        >
          <Paperclip className="w-4 h-4" />
        </button>

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isProcessing}
          placeholder={isProcessing ? 'Processing…' : 'Ask me about invoices, or type a command…'}
          rows={1}
          className="flex-1 resize-none text-sm text-slate-700 placeholder:text-slate-400 outline-none disabled:opacity-50 max-h-32 leading-relaxed"
          style={{ height: 'auto' }}
          onInput={(e) => {
            const t = e.currentTarget
            t.style.height = 'auto'
            t.style.height = `${Math.min(t.scrollHeight, 128)}px`
          }}
        />

        <button
          onClick={() => sendTextMessage(input)}
          disabled={!input.trim() || isProcessing}
          className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0"
        >
          {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) {
              handleFileSelected(file)
              e.target.value = ''
            }
          }}
        />
      </div>
    </div>
  )
}

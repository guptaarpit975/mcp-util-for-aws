import { FormEvent, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Send, Wrench } from 'lucide-react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../lib/api'
import type { ChatEvent } from '../lib/types'

type DisplayMessage = { role: 'user' | 'assistant'; content: string }

function AssistantMarkdown({ content }: { content: string }) {
  return <div className="markdown-body">
    <Markdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ node, ...properties }) => {
          void node
          return <a {...properties} target="_blank" rel="noreferrer" />
        },
      }}
    >
      {content}
    </Markdown>
  </div>
}

export function ChatPage() {
  const queryClient = useQueryClient()
  const conversations = useQuery({ queryKey: ['conversations'], queryFn: api.conversations })
  const [conversationId, setConversationId] = useState<string | null>(null)
  const messages = useQuery({
    queryKey: ['messages', conversationId],
    queryFn: () => api.messages(conversationId!),
    enabled: Boolean(conversationId),
  })
  const [display, setDisplay] = useState<DisplayMessage[]>([])
  const [prompt, setPrompt] = useState('')
  const [activity, setActivity] = useState<ChatEvent[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!conversationId && conversations.data?.length) setConversationId(conversations.data[0].id)
  }, [conversationId, conversations.data])
  useEffect(() => {
    if (!running && messages.data) {
      setDisplay(messages.data.map(({ role, content }) => ({ role, content })))
    }
  }, [messages.data, running])

  const create = useMutation({
    mutationFn: () => api.createConversation(),
    onSuccess: (value) => {
      setConversationId(value.id)
      setDisplay([])
      setActivity([])
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
  })

  async function send(event: FormEvent) {
    event.preventDefault()
    const content = prompt.trim()
    if (!content || running) return
    setPrompt('')
    setError('')
    setActivity([])
    setRunning(true)
    let id = conversationId
    try {
      if (!id) {
        const conversation = await api.createConversation()
        id = conversation.id
        setConversationId(id)
      }
      setDisplay((current) => [...current, { role: 'user', content }])
      await api.streamMessage(id, content, (value) => {
        if (value.type === 'message' && value.content) {
          setDisplay((current) => [...current, { role: 'assistant', content: value.content! }])
        } else if (value.type === 'error') {
          setError(value.message ?? 'The conversation failed.')
        } else if (value.type !== 'done') {
          setActivity((current) => [...current, value])
        }
      })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['messages', id] }),
        queryClient.invalidateQueries({ queryKey: ['conversations'] }),
      ])
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The conversation failed.')
    } finally {
      setRunning(false)
    }
  }

  return <div className="page-stack chat-page">
    <header className="page-header"><div><p className="eyebrow">Read-only AWS copilot</p><h1>Ask OpsLens</h1></div><button className="secondary-button" onClick={() => create.mutate()}><Plus size={15} /> New conversation</button></header>
    <div className="chat-layout">
      <aside className="panel conversation-list">
        <h2>Conversations</h2>
        {conversations.data?.map((item) => <button key={item.id} className={item.id === conversationId ? 'selected' : ''} onClick={() => { setConversationId(item.id); setActivity([]); setError('') }}>{item.title}</button>)}
        {!conversations.data?.length && <p className="muted">Your first question creates a conversation.</p>}
      </aside>
      <section className="panel chat-panel">
        <div className="message-list">
          {!display.length && <div className="empty-chat"><h2>Ask about your AWS environment</h2><p>For example: “Are any ECS services degraded?” or “Find this reference ID in CloudWatch logs.”</p></div>}
          {display.map((item, index) => <article key={`${index}-${item.role}`} className={`chat-message ${item.role}`}><small>{item.role === 'user' ? 'You' : 'OpsLens'}</small>{item.role === 'assistant' ? <AssistantMarkdown content={item.content} /> : <p>{item.content}</p>}</article>)}
          {activity.length > 0 && <div className="agent-activity"><strong><Wrench size={14} /> Agent activity</strong>{activity.slice(-5).map((item, index) => <span key={index}>{item.type === 'tool_started' ? `Calling ${item.tool}` : item.type === 'tool_completed' ? `${item.tool} ${item.status} (${item.duration_ms} ms)` : item.message}</span>)}</div>}
          {running && <p className="muted">Working through the evidence…</p>}
          {error && <div className="notice error">{error}</div>}
        </div>
        <form className="chat-composer" onSubmit={send}><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Ask a question about AWS…" rows={3} /><button className="primary-button" disabled={running || !prompt.trim()}><Send size={15} /> Send</button></form>
      </section>
    </div>
  </div>
}

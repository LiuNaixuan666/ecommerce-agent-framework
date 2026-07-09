import React, { useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, FileText, MessageCircle, RefreshCw, Send, Upload } from 'lucide-react'
import { fetchChatResponse, listUploadTasks, uploadKnowledge, UploadTask, ChatResponseData } from '../services/api'

interface MessageMeta {
  intent?: string
  confidence?: number
  riskLevel?: string
  autoSendAllowed?: boolean
  autoSendBlockers?: string[]
  requiresHumanReview?: boolean
  handoffReason?: string | null
  missingInfo?: string[]
  sources?: string[]
  retrievalType?: string
}

interface Message {
  id: string
  content: string
  isUser: boolean
  timestamp: Date
  meta?: MessageMeta
}

interface Conversation {
  id: string
  messages: Message[]
  createdAt: Date
}

const merchantId = 'default'

const riskLabels: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

const blockerLabels: Record<string, string> = {
  clarification_required: '需要澄清',
  intent_not_clear: '意图不明确',
  evidence_not_focused: '证据不聚焦',
  human_review_required: '需要人工审核',
  missing_info: '缺少关键信息',
  low_confidence: '置信度较低',
  no_evidence: '没有可用依据',
  low_evidence_focus: '资料匹配度不足',
  risk_medium: '中风险问题',
  risk_high: '高风险问题',
}

const toMessageMeta = (response: ChatResponseData): MessageMeta => ({
  intent: response.intent,
  confidence: response.confidence,
  riskLevel: response.risk_level,
  autoSendAllowed: response.auto_send_allowed,
  autoSendBlockers: response.auto_send_blockers || [],
  requiresHumanReview: response.requires_human_review,
  handoffReason: response.handoff_reason,
  missingInfo: response.missing_info || [],
  sources: response.sources || [],
  retrievalType: response.retrieval_type,
})

const ChatInterface: React.FC = () => {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null)
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [uploadTasks, setUploadTasks] = useState<UploadTask[]>([])
  const [taskError, setTaskError] = useState<string | null>(null)
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [notification, setNotification] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const currentConversation = conversations.find((conversation) => conversation.id === currentConversationId)
  const selectedTask = uploadTasks.find((task) => task.upload_id === selectedTaskId) || uploadTasks[0] || null
  const activeTasks = uploadTasks.filter((task) => task.status === 'pending' || task.status === 'processing')

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [currentConversation?.messages])

  useEffect(() => {
    refreshUploadTasks()
  }, [])

  useEffect(() => {
    if (!activeTasks.length) return
    const timer = window.setInterval(() => {
      refreshUploadTasks()
    }, 5000)
    return () => window.clearInterval(timer)
  }, [activeTasks.length])

  const notify = (message: string) => {
    setNotification(message)
    window.setTimeout(() => setNotification(null), 4000)
  }

  const createNewConversation = () => {
    const newConversation: Conversation = {
      id: `local-${Date.now()}`,
      messages: [],
      createdAt: new Date(),
    }
    setConversations((prev) => [newConversation, ...prev])
    setCurrentConversationId(newConversation.id)
  }

  const refreshUploadTasks = async () => {
    try {
      setTaskError(null)
      const tasks = await listUploadTasks(merchantId)
      const sorted = [...tasks].sort((a, b) => {
        const left = a.updated_at ? new Date(a.updated_at).getTime() : 0
        const right = b.updated_at ? new Date(b.updated_at).getTime() : 0
        return right - left
      })
      setUploadTasks(sorted)
      if (sorted.length && !selectedTaskId) {
        setSelectedTaskId(sorted[0].upload_id)
      }
    } catch (error) {
      setTaskError('获取上传任务失败，请稍后重试。')
      console.error('refreshUploadTasks error:', error)
    }
  }

  const appendMessage = (conversationId: string, message: Message) => {
    setConversations((prev) =>
      prev.map((conversation) =>
        conversation.id === conversationId
          ? { ...conversation, messages: [...conversation.messages, message] }
          : conversation,
      ),
    )
  }

  const migrateConversationId = (oldId: string, newId: string) => {
    if (oldId === newId) return newId
    setConversations((prev) =>
      prev.map((conversation) =>
        conversation.id === oldId
          ? { ...conversation, id: newId }
          : conversation,
      ),
    )
    setCurrentConversationId(newId)
    return newId
  }

  const sendMessage = async () => {
    const trimmed = inputMessage.trim()
    if (!trimmed || !currentConversationId) return

    const conversationIdAtSend = currentConversationId
    appendMessage(conversationIdAtSend, {
      id: `${Date.now()}-user`,
      content: trimmed,
      isUser: true,
      timestamp: new Date(),
    })
    setInputMessage('')
    setIsLoading(true)

    try {
      const response = await fetchChatResponse({
        merchant_id: merchantId,
        user_query: trimmed,
        conversation_id: conversationIdAtSend.startsWith('local-') ? null : conversationIdAtSend,
      })

      const targetConversationId = response.conversation_id
        ? migrateConversationId(conversationIdAtSend, response.conversation_id)
        : conversationIdAtSend

      appendMessage(targetConversationId, {
        id: `${Date.now()}-assistant`,
        content: response.recommended_reply || response.response_text || '抱歉，暂时没有获取到回答。',
        isUser: false,
        timestamp: new Date(),
        meta: toMessageMeta(response),
      })
    } catch (error) {
      console.error('发送消息失败:', error)
      appendMessage(conversationIdAtSend, {
        id: `${Date.now()}-error`,
        content: '抱歉，发送消息时出现错误，请稍后重试。',
        isUser: false,
        timestamp: new Date(),
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return

    const formData = new FormData()
    formData.append('merchant_id', merchantId)
    Array.from(files).forEach((file) => {
      formData.append('files', file)
    })

    try {
      const result = await uploadKnowledge(formData)
      notify(`已创建上传任务 ${result.upload_id}，系统正在解析文档。`)
      await refreshUploadTasks()
    } catch (error) {
      console.error('上传文件失败:', error)
      notify('上传失败，请检查文件格式并重试。')
    } finally {
      event.target.value = ''
    }
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendMessage()
    }
  }

  const renderDecisionPanel = (meta?: MessageMeta) => {
    if (!meta) return null

    const autoAllowed = Boolean(meta.autoSendAllowed)
    const blockers = meta.autoSendBlockers || []
    const riskLevel = meta.riskLevel || 'unknown'

    return (
      <div style={{ marginTop: '0.75rem', borderTop: '1px solid rgba(15, 23, 42, 0.12)', paddingTop: '0.75rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              borderRadius: '999px',
              padding: '0.25rem 0.55rem',
              backgroundColor: autoAllowed ? '#dcfce7' : '#fee2e2',
              color: autoAllowed ? '#166534' : '#991b1b',
              fontSize: '0.75rem',
              fontWeight: 600,
            }}
          >
            {autoAllowed ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
            {autoAllowed ? '允许自动发送' : '转人工/不自动发送'}
          </span>
          <span style={{ fontSize: '0.75rem', color: '#475569' }}>
            风险：{riskLabels[riskLevel] || riskLevel}
          </span>
          {typeof meta.confidence === 'number' && (
            <span style={{ fontSize: '0.75rem', color: '#475569' }}>
              置信度：{Math.round(meta.confidence * 100)}%
            </span>
          )}
          {meta.intent && (
            <span style={{ fontSize: '0.75rem', color: '#475569' }}>
              意图：{meta.intent}
            </span>
          )}
        </div>

        {blockers.length > 0 && (
          <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#7f1d1d' }}>
            阻止原因：{blockers.map((item) => blockerLabels[item] || item).join('、')}
          </div>
        )}
        {meta.handoffReason && (
          <div style={{ marginTop: '0.35rem', fontSize: '0.75rem', color: '#7f1d1d' }}>
            转人工原因：{meta.handoffReason}
          </div>
        )}
        {meta.missingInfo && meta.missingInfo.length > 0 && (
          <div style={{ marginTop: '0.35rem', fontSize: '0.75rem', color: '#854d0e' }}>
            缺失信息：{meta.missingInfo.join('、')}
          </div>
        )}
        {meta.sources && meta.sources.length > 0 && (
          <div style={{ marginTop: '0.35rem', fontSize: '0.75rem', color: '#475569' }}>
            来源：{meta.sources.join('、')}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: '600px', backgroundColor: 'white', borderRadius: '0.5rem', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)' }}>
      <aside style={{ width: '256px', backgroundColor: '#f9fafb', borderRight: '1px solid #e5e7eb', padding: '1rem', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ fontSize: '1.125rem', fontWeight: 600 }}>会话</h2>
          <button onClick={createNewConversation} style={{ padding: '0.5rem', backgroundColor: '#2563eb', color: 'white', borderRadius: '0.375rem', border: 'none', cursor: 'pointer' }} title="新建会话">
            <MessageCircle size={16} />
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              onClick={() => setCurrentConversationId(conversation.id)}
              style={{ width: '100%', textAlign: 'left', padding: '0.75rem', borderRadius: '0.375rem', border: '1px solid #d1d5db', backgroundColor: conversation.id === currentConversationId ? '#dbeafe' : 'white', cursor: 'pointer' }}
            >
              <div style={{ fontSize: '0.875rem', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                会话 {conversation.id.slice(-6)}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                {conversation.messages.length} 条消息
              </div>
            </button>
          ))}
        </div>

        <section style={{ marginTop: '1.5rem' }}>
          <h3 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem' }}>知识库管理</h3>
          <label style={{ display: 'block' }}>
            <input type="file" multiple onChange={handleFileUpload} style={{ display: 'none' }} accept=".txt,.md,.markdown,.pdf,.docx,.csv" />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', padding: '0.75rem', border: '2px dashed #d1d5db', borderRadius: '0.375rem', cursor: 'pointer' }}>
              <Upload size={16} style={{ marginRight: '0.5rem' }} />
              <span style={{ fontSize: '0.875rem' }}>上传文档</span>
            </div>
          </label>

          <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.8rem', color: '#475569' }}>最近任务</p>
            <button onClick={refreshUploadTasks} style={{ border: 'none', backgroundColor: '#e0e7ff', color: '#3730a3', borderRadius: '0.5rem', padding: '0.45rem 0.75rem', cursor: 'pointer' }} title="刷新上传任务">
              <RefreshCw size={14} />
            </button>
          </div>

          {selectedTask && (
            <div style={{ marginTop: '0.75rem', padding: '0.75rem', borderRadius: '0.75rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: '#334155', fontSize: '0.82rem' }}>
                <FileText size={16} />
                <span>当前任务：{selectedTask.upload_id.slice(0, 10)}...</span>
              </div>
              <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#475569' }}>
                状态：{selectedTask.status} · 文件：{selectedTask.files_received} · 文档：{selectedTask.documents_processed} · Chunks：{selectedTask.chunks_created}
              </div>
            </div>
          )}

          {taskError && <p style={{ marginTop: '0.75rem', fontSize: '0.82rem', color: '#b91c1c' }}>{taskError}</p>}

          <div style={{ marginTop: '0.75rem', display: 'grid', gap: '0.75rem' }}>
            {uploadTasks.length > 0 ? uploadTasks.map((task) => (
              <button
                key={task.upload_id}
                onClick={() => setSelectedTaskId(task.upload_id)}
                style={{ width: '100%', textAlign: 'left', padding: '0.85rem', borderRadius: '0.75rem', border: selectedTaskId === task.upload_id ? '1px solid #2563eb' : '1px solid #e2e8f0', backgroundColor: selectedTaskId === task.upload_id ? '#eff6ff' : 'white', cursor: 'pointer' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#0f172a' }}>{task.upload_id.slice(0, 10)}...</span>
                  <span style={{ fontSize: '0.75rem', color: '#334155', backgroundColor: task.status === 'completed' ? '#dcfce7' : task.status === 'failed' ? '#fee2e2' : '#eef6ff', borderRadius: '999px', padding: '0.2rem 0.55rem' }}>
                    {task.status}
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: '#475569', lineHeight: 1.5 }}>
                  {task.files_received} 个文件 · {task.documents_processed} 篇文档
                </div>
              </button>
            )) : (
              <div style={{ padding: '0.9rem', borderRadius: '0.75rem', backgroundColor: '#f8fafc', border: '1px dashed #cbd5e1', color: '#475569' }}>
                暂无知识库任务。上传文档后会显示在这里。
              </div>
            )}
          </div>
        </section>
      </aside>

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {currentConversation ? (
          <>
            <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {currentConversation.messages.map((message) => (
                <div key={message.id} style={{ display: 'flex', justifyContent: message.isUser ? 'flex-end' : 'flex-start' }}>
                  <div className={`message ${message.isUser ? 'message-user' : 'message-bot'}`} style={{ maxWidth: '78%' }}>
                    <p style={{ whiteSpace: 'pre-wrap' }}>{message.content}</p>
                    {renderDecisionPanel(message.meta)}
                    <p style={{ fontSize: '0.75rem', opacity: 0.7, marginTop: '0.25rem' }}>
                      {message.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <div className="message message-bot">
                    <span style={{ fontSize: '0.875rem' }}>正在思考...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div style={{ borderTop: '1px solid #e5e7eb', padding: '1rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input type="text" value={inputMessage} onChange={(event) => setInputMessage(event.target.value)} onKeyDown={handleKeyDown} placeholder="输入你的问题..." className="input" style={{ flex: 1 }} disabled={isLoading} />
                <button onClick={sendMessage} disabled={isLoading || !inputMessage.trim()} className="btn btn-primary" style={{ padding: '0.5rem' }} title="发送">
                  <Send size={16} />
                </button>
              </div>
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ textAlign: 'center' }}>
              <MessageCircle size={48} style={{ color: '#d1d5db', marginBottom: '1rem' }} />
              <h3 style={{ fontSize: '1.125rem', fontWeight: 500, color: '#111827', marginBottom: '0.5rem' }}>
                开始新对话
              </h3>
              <p style={{ color: '#6b7280', marginBottom: '1rem' }}>选择或创建一个会话来开始测试客服问答。</p>
              <button onClick={createNewConversation} className="btn btn-primary" style={{ padding: '0.75rem 1.5rem' }}>
                新建会话
              </button>
            </div>
          </div>
        )}

        {notification && (
          <div style={{ position: 'fixed', right: '1.5rem', bottom: '1.5rem', backgroundColor: '#111827', color: '#ffffff', padding: '0.9rem 1rem', borderRadius: '0.85rem', boxShadow: '0 15px 30px rgba(15, 23, 42, 0.18)', zIndex: 20 }}>
            {notification}
          </div>
        )}
      </main>
    </div>
  )
}

export default ChatInterface

import React, { useState, useRef, useEffect } from 'react'
import { Send, Upload, MessageCircle, RefreshCw, FileText } from 'lucide-react'
import { fetchChatResponse, uploadKnowledge, listUploadTasks, UploadTask } from '../services/api'

interface Message {
  id: string
  content: string
  isUser: boolean
  timestamp: Date
}

interface Conversation {
  id: string
  messages: Message[]
  createdAt: Date
}

const merchantId = 'default'

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

  const currentConversation = conversations.find(c => c.id === currentConversationId)
  const selectedTask = uploadTasks.find(task => task.upload_id === selectedTaskId) || uploadTasks[0] || null
  const activeTasks = uploadTasks.filter(task => task.status === 'pending' || task.status === 'processing')

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [currentConversation?.messages])

  useEffect(() => {
    refreshUploadTasks()
  }, [])

  useEffect(() => {
    if (!activeTasks.length) {
      return
    }

    const timer = window.setInterval(() => {
      refreshUploadTasks()
    }, 5000)

    return () => {
      window.clearInterval(timer)
    }
  }, [activeTasks.length])

  const notify = (message: string) => {
    setNotification(message)
    window.setTimeout(() => setNotification(null), 4000)
  }

  const createNewConversation = () => {
    const newConversation: Conversation = {
      id: Date.now().toString(),
      messages: [],
      createdAt: new Date()
    }

    setConversations(prev => [newConversation, ...prev])
    setCurrentConversationId(newConversation.id)
  }

  const selectConversation = (conversationId: string) => {
    setCurrentConversationId(conversationId)
  }

  const refreshUploadTasks = async () => {
    try {
      setTaskError(null)
      const tasks = await listUploadTasks(merchantId)
      const sorted = tasks.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      setUploadTasks(sorted)
      if (sorted.length && !selectedTaskId) {
        setSelectedTaskId(sorted[0].upload_id)
      }
    } catch (error) {
      setTaskError('获取上传任务失败，请稍后重试。')
      console.error('refreshUploadTasks error:', error)
    }
  }

  const sendMessage = async () => {
    if (!inputMessage.trim() || !currentConversationId) return

    const userMessage: Message = {
      id: `${Date.now()}-user`,
      content: inputMessage,
      isUser: true,
      timestamp: new Date()
    }

    setConversations(prev => prev.map(conv =>
      conv.id === currentConversationId
        ? { ...conv, messages: [...conv.messages, userMessage] }
        : conv
    ))

    setInputMessage('')
    setIsLoading(true)

    try {
      const response = await fetchChatResponse({
        merchant_id: merchantId,
        user_query: inputMessage,
        conversation_id: currentConversationId
      })

      if (response.conversation_id && response.conversation_id !== currentConversationId) {
        setCurrentConversationId(response.conversation_id)
      }

      const botMessage: Message = {
        id: `${Date.now()}-assistant`,
        content: response.response_text || '抱歉，未获取到回答。',
        isUser: false,
        timestamp: new Date()
      }

      setConversations(prev => prev.map(conv =>
        conv.id === currentConversationId
          ? { ...conv, messages: [...conv.messages, botMessage] }
          : conv
      ))
    } catch (error) {
      console.error('发送消息失败:', error)
      const errorMessage: Message = {
        id: `${Date.now()}-error`,
        content: '抱歉，发送消息时出现错误。请稍后重试。',
        isUser: false,
        timestamp: new Date()
      }

      setConversations(prev => prev.map(conv =>
        conv.id === currentConversationId
          ? { ...conv, messages: [...conv.messages, errorMessage] }
          : conv
      ))
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files) return

    const formData = new FormData()
    formData.append('merchant_id', merchantId)
    Array.from(files).forEach(file => {
      formData.append('files', file)
    })

    try {
      const result = await uploadKnowledge(formData)
      notify(`已创建上传任务 ${result.upload_id}，摄取已自动开始。`)
      await refreshUploadTasks()
    } catch (error) {
      console.error('上传文件失败:', error)
      notify('上传失败，请检查文件格式并重试。')
    }
  }

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendMessage()
    }
  }

  return (
    <div style={{
      display: 'flex',
      height: '600px',
      backgroundColor: 'white',
      borderRadius: '0.5rem',
      boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
    }}>
      {/* 侧边栏 - 会话列表 */}
      <div style={{
        width: '256px',
        backgroundColor: '#f9fafb',
        borderRight: '1px solid #e5e7eb',
        padding: '1rem'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ fontSize: '1.125rem', fontWeight: '600' }}>会话</h2>
          <button
            onClick={createNewConversation}
            style={{
              padding: '0.5rem',
              backgroundColor: '#3b82f6',
              color: 'white',
              borderRadius: '0.375rem',
              border: 'none',
              cursor: 'pointer'
            }}
            title="新建会话"
          >
            <MessageCircle size={16} />
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {conversations.map(conv => (
            <button
              key={conv.id}
              onClick={() => selectConversation(conv.id)}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '0.75rem',
                borderRadius: '0.375rem',
                border: '1px solid #d1d5db',
                backgroundColor: conv.id === currentConversationId ? '#dbeafe' : 'white',
                cursor: 'pointer',
                transition: 'background-color 0.2s'
              }}
            >
              <div style={{ fontSize: '0.875rem', fontWeight: '500', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                会话 {conv.id.slice(-4)}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                {conv.messages.length} 条消息
              </div>
            </button>
          ))}
        </div>

        {/* 文件上传区域 */}
        <div style={{ marginTop: '1.5rem' }}>
          <h3 style={{ fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>知识库管理</h3>
          <label style={{ display: 'block' }}>
            <input
              type="file"
              multiple
              onChange={handleFileUpload}
              style={{ display: 'none' }}
              accept=".txt,.pdf,.doc,.docx,.csv"
            />
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              padding: '0.75rem',
              border: '2px dashed #d1d5db',
              borderRadius: '0.375rem',
              cursor: 'pointer',
              transition: 'border-color 0.2s'
            }}>
              <Upload size={16} style={{ marginRight: '0.5rem' }} />
              <span style={{ fontSize: '0.875rem' }}>上传文档</span>
            </div>
          </label>

          <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p style={{ margin: 0, fontSize: '0.8rem', color: '#475569' }}>最近任务</p>
            </div>
            <button
              onClick={refreshUploadTasks}
              style={{
                border: 'none',
                backgroundColor: '#e0e7ff',
                color: '#3730a3',
                borderRadius: '0.5rem',
                padding: '0.45rem 0.75rem',
                cursor: 'pointer'
              }}
            >
              <RefreshCw size={14} />
            </button>
          </div>

          {selectedTask && (
            <div style={{ marginTop: '0.75rem', padding: '0.75rem', borderRadius: '0.75rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: '#334155', fontSize: '0.82rem' }}>
                <FileText size={16} />
                <span>当前选中任务：{selectedTask.upload_id.slice(0, 10)}...</span>
              </div>
              <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#475569' }}>
                状态：{selectedTask.status} · 文件：{selectedTask.files_received} · 文档：{selectedTask.documents_processed}
              </div>
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '0.35rem' }}>
                更新于 {new Date(selectedTask.updated_at).toLocaleTimeString('zh-CN', { hour12: false })}
              </div>
            </div>
          )}

          {taskError && (
            <p style={{ marginTop: '0.75rem', fontSize: '0.82rem', color: '#b91c1c' }}>{taskError}</p>
          )}

          <div style={{ marginTop: '0.75rem', display: 'grid', gap: '0.75rem' }}>
            {uploadTasks.length > 0 ? uploadTasks.map(task => {
              const statusClass = task.status === 'completed'
                ? '#dcfce7'
                : task.status === 'failed'
                  ? '#fee2e2'
                  : '#eef6ff'

              return (
                <button
                  key={task.upload_id}
                  onClick={() => setSelectedTaskId(task.upload_id)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '0.85rem',
                    borderRadius: '0.75rem',
                    border: selectedTaskId === task.upload_id ? '1px solid #2563eb' : '1px solid #e2e8f0',
                    backgroundColor: selectedTaskId === task.upload_id ? '#eff6ff' : 'white',
                    cursor: 'pointer'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#0f172a' }}>{task.upload_id.slice(0, 10)}...</span>
                    <span style={{ fontSize: '0.75rem', color: '#334155', backgroundColor: statusClass, borderRadius: '999px', padding: '0.2rem 0.55rem' }}>
                      {task.status}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#475569', lineHeight: 1.5 }}>
                    {task.files_received} 个文件 · {task.documents_processed} 文档
                  </div>
                </button>
              )
            }) : (
              <div style={{ padding: '0.9rem', borderRadius: '0.75rem', backgroundColor: '#f8fafc', border: '1px dashed #cbd5e1', color: '#475569' }}>
                暂无知识库任务。上传文档后将在此显示。
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 主聊天区域 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {currentConversation ? (
          <>
            {/* 消息列表 */}
            <div style={{
              flex: 1,
              overflowY: 'auto',
              padding: '1rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem'
            }}>
              {currentConversation.messages.map(message => (
                <div
                  key={message.id}
                  style={{
                    display: 'flex',
                    justifyContent: message.isUser ? 'flex-end' : 'flex-start'
                  }}
                >
                  <div className={`message ${message.isUser ? 'message-user' : 'message-bot'}`}>
                    <p style={{ whiteSpace: 'pre-wrap' }}>{message.content}</p>
                    <p style={{ fontSize: '0.75rem', opacity: 0.7, marginTop: '0.25rem' }}>
                      {message.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <div className="message message-bot">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <div className="animate-spin" style={{
                        width: '1rem',
                        height: '1rem',
                        borderTop: '2px solid #6b7280'
                      }}></div>
                      <span style={{ fontSize: '0.875rem' }}>正在思考...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* 输入区域 */}
            <div style={{
              borderTop: '1px solid #e5e7eb',
              padding: '1rem'
            }}>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="输入您的问题..."
                  className="input"
                  style={{ flex: 1 }}
                  disabled={isLoading}
                />
                <button
                  onClick={sendMessage}
                  disabled={isLoading || !inputMessage.trim()}
                  className="btn btn-primary"
                  style={{ padding: '0.5rem' }}
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          </>
        ) : (
          <div style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <div style={{ textAlign: 'center' }}>
              <MessageCircle size={48} style={{ color: '#d1d5db', marginBottom: '1rem' }} />
              <h3 style={{ fontSize: '1.125rem', fontWeight: '500', color: '#111827', marginBottom: '0.5rem' }}>开始新对话</h3>
              <p style={{ color: '#6b7280', marginBottom: '1rem' }}>选择或创建一个会话来开始聊天</p>
              <button
                onClick={createNewConversation}
                className="btn btn-primary"
                style={{ padding: '0.75rem 1.5rem' }}
              >
                新建会话
              </button>
            </div>
          </div>
        )}
      {notification && (
        <div style={{
          position: 'fixed',
          right: '1.5rem',
          bottom: '1.5rem',
          backgroundColor: '#111827',
          color: '#ffffff',
          padding: '0.9rem 1rem',
          borderRadius: '0.85rem',
          boxShadow: '0 15px 30px rgba(15, 23, 42, 0.18)',
          zIndex: 20,
        }}>
          {notification}
        </div>
      )}
      </div>
    </div>
  )
}

export default ChatInterface
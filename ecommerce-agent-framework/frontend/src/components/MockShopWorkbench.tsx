import { useMemo, useState, type CSSProperties } from 'react'
import {
  reportRpaSendResult,
  sendLocalAgentHeartbeat,
  sendRpaMessage,
  type RpaMessageResponse,
} from '../services/api'

type MockMessage = {
  id: string
  role: 'buyer' | 'agent' | 'system'
  text: string
  status?: string
}

const merchantId = 'mock_merchant'
const platform = 'mock_shop'
const conversationId = 'mock-buyer-001'
const agentId = 'local-agent-mock'

export default function MockShopWorkbench() {
  const [messages, setMessages] = useState<MockMessage[]>([
    {
      id: 'seed-1',
      role: 'buyer',
      text: '这款有现货吗？',
      status: 'new',
    },
  ])
  const [draft, setDraft] = useState('这个商品支持几天无理由退货？')
  const [lastDecision, setLastDecision] = useState<RpaMessageResponse | null>(null)
  const [agentStatus, setAgentStatus] = useState('idle')
  const [error, setError] = useState<string | null>(null)

  const productContext = useMemo(
    () => ({
      platform,
      product_name: '儿童科普图书套装',
      sku: 'BOOK-001',
      price: 59.9,
      currency: 'CNY',
      stock: 28,
      stock_status: 'in_stock',
      url: 'https://mock.shop/products/book-001',
    }),
    [],
  )

  const addBuyerMessage = () => {
    const text = draft.trim()
    if (!text) return
    setMessages((current) => [
      ...current,
      {
        id: `buyer-${Date.now()}`,
        role: 'buyer',
        text,
        status: 'new',
      },
    ])
    setDraft('')
    setLastDecision(null)
  }

  const processLatestBuyerMessage = async () => {
    setError(null)
    setAgentStatus('running')

    try {
      await sendLocalAgentHeartbeat({
        agent_id: agentId,
        merchant_id: merchantId,
        platform,
        shop_id: 'mock-shop-001',
        status: 'running',
        watched_window_title: 'Mock 电商客服工作台',
      })

      const latest = [...messages].reverse().find((item) => item.role === 'buyer' && item.status === 'new')
      if (!latest) {
        setAgentStatus('idle')
        return
      }

      const decision = await sendRpaMessage({
        merchant_id: merchantId,
        platform,
        external_conversation_id: conversationId,
        external_message_id: latest.id,
        customer_message: latest.text,
        customer_id: 'mock-buyer-001',
        customer_name: '模拟买家',
        page_context: productContext,
        metadata: {
          agent_id: agentId,
          agent_type: 'self_built_local_agent',
          adapter: 'MockShopAdapter',
          watcher_type: 'mock_dom',
        },
      })

      setLastDecision(decision)
      setMessages((current) =>
        current.map((item) =>
          item.id === latest.id
            ? {
                ...item,
                status: decision.decision.auto_send_allowed ? 'processed' : 'handoff_required',
              }
            : item,
        ),
      )

      if (decision.decision.auto_send_allowed && decision.rpa_instruction.send_text) {
        setMessages((current) => [
          ...current,
          {
            id: `agent-${Date.now()}`,
            role: 'agent',
            text: decision.rpa_instruction.send_text || '',
            status: 'auto_sent',
          },
        ])

        await reportRpaSendResult({
          request_id: decision.request_id,
          merchant_id: merchantId,
          platform,
          external_conversation_id: conversationId,
          external_message_id: latest.id,
          send_status: 'success',
          sent_text: decision.rpa_instruction.send_text,
          agent_id: agentId,
        })
      } else {
        setMessages((current) => [
          ...current,
          {
            id: `system-${Date.now()}`,
            role: 'system',
            text: `已转人工：${decision.rpa_instruction.handoff_note || decision.decision.handoff_reason || '后端策略不允许自动发送'}`,
            status: 'handoff',
          },
        ])

        await reportRpaSendResult({
          request_id: decision.request_id,
          merchant_id: merchantId,
          platform,
          external_conversation_id: conversationId,
          external_message_id: latest.id,
          send_status: 'handoff',
          agent_id: agentId,
          error_code: 'AUTO_SEND_BLOCKED',
          error_message: decision.rpa_instruction.handoff_note || decision.decision.handoff_reason || 'auto send blocked',
        })
      }

      setAgentStatus('idle')
    } catch (err) {
      setAgentStatus('error')
      setError(err instanceof Error ? err.message : '处理失败')
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '260px minmax(0, 1fr) 320px', gap: '1rem' }}>
      <aside style={panelStyle}>
        <h2 style={sectionTitleStyle}>会话</h2>
        <div style={conversationItemStyle}>
          <strong>模拟买家</strong>
          <span style={mutedStyle}>Mock 电商客服工作台</span>
        </div>
        <div style={{ marginTop: '1rem', fontSize: '0.875rem', color: '#475569' }}>
          Agent 状态：<strong>{agentStatus}</strong>
        </div>
      </aside>

      <section style={panelStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <h2 style={sectionTitleStyle}>Mock 客服窗口</h2>
            <div style={mutedStyle}>用于稳定验证 Local Agent 闭环</div>
          </div>
          <button style={primaryButtonStyle} onClick={processLatestBuyerMessage}>
            运行一次 Local Agent
          </button>
        </div>

        <div style={messageListStyle}>
          {messages.map((message) => (
            <div
              key={message.id}
              style={{
                ...messageBubbleStyle,
                alignSelf: message.role === 'buyer' ? 'flex-start' : 'flex-end',
                background: message.role === 'buyer' ? '#eef2ff' : message.role === 'agent' ? '#ecfdf5' : '#fff7ed',
                borderColor: message.role === 'buyer' ? '#c7d2fe' : message.role === 'agent' ? '#bbf7d0' : '#fed7aa',
              }}
            >
              <div style={{ fontWeight: 600 }}>{roleLabel(message.role)}</div>
              <div>{message.text}</div>
              {message.status && <div style={statusStyle}>{message.status}</div>}
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="输入一条模拟买家消息"
            style={inputStyle}
          />
          <button style={secondaryButtonStyle} onClick={addBuyerMessage}>
            添加买家消息
          </button>
        </div>
        {error && <div style={{ marginTop: '0.75rem', color: '#b91c1c' }}>{error}</div>}
      </section>

      <aside style={panelStyle}>
        <h2 style={sectionTitleStyle}>商品上下文</h2>
        <dl style={{ display: 'grid', gap: '0.5rem', fontSize: '0.875rem' }}>
          <Info label="商品" value={String(productContext.product_name)} />
          <Info label="SKU" value={String(productContext.sku)} />
          <Info label="价格" value={`¥${productContext.price}`} />
          <Info label="库存" value={`${productContext.stock} (${productContext.stock_status})`} />
        </dl>

        <h2 style={{ ...sectionTitleStyle, marginTop: '1.5rem' }}>后端决策</h2>
        {lastDecision ? (
          <div style={{ display: 'grid', gap: '0.5rem', fontSize: '0.875rem' }}>
            <Info label="动作" value={lastDecision.decision.action} />
            <Info label="自动发送" value={lastDecision.decision.auto_send_allowed ? '允许' : '禁止'} />
            <Info label="风险" value={lastDecision.decision.risk_level || '-'} />
            <Info label="置信度" value={formatConfidence(lastDecision.decision.confidence)} />
            <Info label="阻止原因" value={lastDecision.decision.auto_send_blockers.join(', ') || '-'} />
          </div>
        ) : (
          <div style={mutedStyle}>还没有处理新消息</div>
        )}
      </aside>
    </div>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt style={{ color: '#64748b' }}>{label}</dt>
      <dd style={{ color: '#0f172a', fontWeight: 600 }}>{value}</dd>
    </div>
  )
}

function roleLabel(role: MockMessage['role']) {
  if (role === 'buyer') return '买家'
  if (role === 'agent') return 'AI 客服'
  return '系统'
}

function formatConfidence(value?: number) {
  if (typeof value !== 'number') return '-'
  return `${Math.round(value * 100)}%`
}

const panelStyle: CSSProperties = {
  background: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: 8,
  padding: '1rem',
  minHeight: '32rem',
}

const sectionTitleStyle: CSSProperties = {
  fontSize: '1rem',
  lineHeight: 1.4,
  color: '#0f172a',
  marginBottom: '0.5rem',
}

const mutedStyle: CSSProperties = {
  color: '#64748b',
  fontSize: '0.875rem',
}

const conversationItemStyle: CSSProperties = {
  display: 'grid',
  gap: '0.25rem',
  border: '1px solid #cbd5e1',
  borderRadius: 8,
  padding: '0.75rem',
  background: '#f8fafc',
}

const messageListStyle: CSSProperties = {
  minHeight: '24rem',
  maxHeight: '24rem',
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: '0.75rem',
  padding: '0.75rem',
  background: '#f8fafc',
  border: '1px solid #e2e8f0',
  borderRadius: 8,
}

const messageBubbleStyle: CSSProperties = {
  maxWidth: '72%',
  border: '1px solid',
  borderRadius: 8,
  padding: '0.75rem',
  lineHeight: 1.5,
}

const statusStyle: CSSProperties = {
  marginTop: '0.25rem',
  color: '#64748b',
  fontSize: '0.75rem',
}

const inputStyle: CSSProperties = {
  flex: 1,
  border: '1px solid #cbd5e1',
  borderRadius: 8,
  padding: '0.75rem',
}

const primaryButtonStyle: CSSProperties = {
  border: 'none',
  borderRadius: 8,
  background: '#2563eb',
  color: '#ffffff',
  padding: '0.75rem 1rem',
  fontWeight: 600,
  cursor: 'pointer',
}

const secondaryButtonStyle: CSSProperties = {
  border: '1px solid #cbd5e1',
  borderRadius: 8,
  background: '#ffffff',
  color: '#0f172a',
  padding: '0.75rem 1rem',
  fontWeight: 600,
  cursor: 'pointer',
}

import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  Clock,
  ExternalLink,
  LogIn,
  MessageSquare,
  PlayCircle,
  RefreshCw,
  Send,
  ShieldAlert,
  Upload,
  UserRound,
  XCircle,
} from 'lucide-react'
import {
  fetchChatResponse,
  fetchHandoffTickets,
  fetchHandoffSummary,
  fetchProducts,
  resolveHandoffTicket,
  returnHandoffTicketToAi,
  uploadKnowledge,
  type EvidenceSource,
  type HandoffTicket,
  type HandoffSummaryResponse,
  type ProductSummary,
} from '../services/api'

type PlatformDef = {
  code: string
  name: string
  color: string
  status: 'active' | 'beta' | 'coming_soon'
  description: string
}

type BrowserSession = {
  platform: string
  page_type: string
  status: string
  logged_in: boolean
  merchant_id?: string | null
  shop_id?: string | null
  current_url?: string | null
  last_heartbeat_at?: string | null
}

type AgentInfo = {
  agent_id: string
  platform?: string
  status: string
  latest_buyer_message?: string | null
  current_page_url?: string | null
  metadata?: Record<string, unknown> | null
}

type ConversationInfo = {
  conversation_id: string
  platform?: string | null
  external_conversation_id?: string | null
  customer_name?: string | null
  message_count?: number
  last_intent?: string | null
  last_updated?: string | null
  processing_status?: string | null
  last_send_status?: string | null
}

type HistoryMessage = {
  role?: string
  content?: string
  text?: string
  timestamp?: string
  created_at?: string
  metadata?: Record<string, unknown>
}

type WorkTab = 'handoff' | 'rules' | 'learning' | 'simulation'
type AgentMode = 'dry_run' | 'assist' | 'auto'
type HandoffRuleKey = 'keyword' | 'image' | 'after_sale' | 'out_of_knowledge' | 'low_confidence' | 'timeout'

const merchantId = 'default'

const ruleOptions: Array<{ id: HandoffRuleKey; label: string; detail: string }> = [
  { id: 'keyword', label: '关键词命中', detail: '退款、投诉、差评、转账等敏感词进入人工。' },
  { id: 'image', label: '图片消息', detail: '买家只发图片或商品图时先人工确认。' },
  { id: 'after_sale', label: '售后风险', detail: '退款、退货、改地址、催发货等先人工审核。' },
  { id: 'out_of_knowledge', label: '超出知识库', detail: '知识库没有证据时不自动回复。' },
  { id: 'low_confidence', label: '低置信度', detail: 'AI 置信度低于阈值时转人工。' },
  { id: 'timeout', label: '超时兜底', detail: '人工处理超过设定时间后提醒。' },
]

export default function CustomerServiceHub() {
  const [platforms, setPlatforms] = useState<PlatformDef[]>([])
  const [sessions, setSessions] = useState<BrowserSession[]>([])
  const [agents, setAgents] = useState<AgentInfo[]>([])
  // sendResults intentionally not stored — handoffTickets provide the persistent queue
  const [conversations, setConversations] = useState<ConversationInfo[]>([])
  const [history, setHistory] = useState<HistoryMessage[]>([])
  const [selectedPlatform, setSelectedPlatform] = useState('pinduoduo')
  const [selectedConversationId, setSelectedConversationId] = useState<string>('')
  const [activeTab, setActiveTab] = useState<WorkTab>('handoff')
  const [mode, setMode] = useState<AgentMode>('dry_run')
  const [enabledRules, setEnabledRules] = useState<HandoffRuleKey[]>(['keyword', 'image', 'after_sale', 'out_of_knowledge', 'low_confidence', 'timeout'])
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.75)
  const [ruleStatus, setRuleStatus] = useState('')
  const [learningDraft, setLearningDraft] = useState('')
  const [uploadStatus, setUploadStatus] = useState('')
  const [simQuestion, setSimQuestion] = useState('这款还有货吗？')
  const [simAnswer, setSimAnswer] = useState('')
  const [simEvidence, setSimEvidence] = useState<EvidenceSource[]>([])
  const [simLoading, setSimLoading] = useState(false)
  const [simProducts, setSimProducts] = useState<ProductSummary[]>([])
  const [selectedSimProductId, setSelectedSimProductId] = useState('')
  const [simProductStatus, setSimProductStatus] = useState('')
  const [handoffTickets, setHandoffTickets] = useState<HandoffTicket[]>([])
  const [handoffSummary, setHandoffSummary] = useState<HandoffSummaryResponse | null>(null)
  const [statusText, setStatusText] = useState('')

  const selectedPlatformDef = platforms.find((item) => item.code === selectedPlatform)
  const currentSession = sessions.find((item) => item.platform === selectedPlatform && item.page_type === 'chat')
  const currentAgent =
    agents.find((item) => item.agent_id === `${selectedPlatform}-chat`) ||
    agents.find((item) => item.platform === selectedPlatform)
  const agentMeta = (currentAgent?.metadata || {}) as Record<string, any>
  const selectedSimProduct = simProducts.find((item) => item.id === selectedSimProductId)

  const pendingItems = useMemo(() => {
    return handoffTickets
      .filter((t) => t.status === 'pending' || t.status === 'processing')
      .slice(0, 8)
      .map((t) => ({
        id: t.ticket_id,
        ticket: t,
        message: t.customer_message || '需要人工处理',
        reason: t.reason || 'AI 未自动发送',
        platform: t.platform,
        created_at: t.created_at,
      }))
  }, [handoffTickets])

  const selectedConversation = conversations.find((item) => item.conversation_id === selectedConversationId)

  useEffect(() => {
    loadData()
    loadRules()
    const timer = window.setInterval(loadData, 5000)
    return () => window.clearInterval(timer)
  }, [selectedPlatform])

  useEffect(() => {
    if (!selectedConversationId && conversations.length > 0) {
      setSelectedConversationId(conversations[0].conversation_id)
    }
  }, [conversations, selectedConversationId])

  useEffect(() => {
    if (selectedConversationId) {
      loadHistory(selectedConversationId)
    } else {
      setHistory([])
    }
  }, [selectedConversationId])

  useEffect(() => {
    loadSimulationProducts()
  }, [selectedPlatform, currentSession?.shop_id])

  useEffect(() => {
    if (selectedSimProductId && !simProducts.some((item) => item.id === selectedSimProductId)) {
      setSelectedSimProductId('')
    }
  }, [selectedSimProductId, simProducts])

  async function loadData() {
    try {
      const [platformRes, sessionRes, agentRes, convRes, ticketRes, summaryRes] = await Promise.all([
        fetch('/api/platform/list').then((r) => r.json()),
        fetch('/api/platform-browser/sessions').then((r) => r.json()),
        fetch('/api/local-agent/status').then((r) => r.json()),
        fetch(`/api/chat/conversations?merchant_id=${encodeURIComponent(merchantId)}`).then((r) => r.json()),
        fetchHandoffTickets({ merchant_id: merchantId, limit: 50 }),
        fetchHandoffSummary(merchantId),
      ])
      setPlatforms(platformRes.platforms || [])
      setSessions(sessionRes.sessions || [])
      setAgents(agentRes.agents || [])
      setHandoffTickets(ticketRes.tickets || [])
      setHandoffSummary(summaryRes)

      const allConversations: ConversationInfo[] = convRes.conversations || []
      const filtered = allConversations.filter((item) => !item.platform || item.platform === selectedPlatform)
      setConversations(filtered)
    } catch (error) {
      setStatusText(error instanceof Error ? error.message : '刷新工作台失败')
    }
  }

  async function loadRules() {
    try {
      const data = await fetch(`/api/agent-rules?merchant_id=${encodeURIComponent(merchantId)}&platform=${encodeURIComponent(selectedPlatform)}`).then((r) => r.json())
      const rules = data.rules || {}
      if (rules.mode) {
        setMode(rules.mode)
      }
      if (typeof rules.confidence_threshold === 'number') {
        setConfidenceThreshold(rules.confidence_threshold)
      }
      const handoffRules = rules.handoff_rules || {}
      const enabled = ruleOptions
        .filter((rule) => handoffRules[rule.id] !== false)
        .map((rule) => rule.id)
      setEnabledRules(enabled)
      setRuleStatus('')
    } catch {
      setRuleStatus('规则读取失败，将使用页面默认规则')
    }
  }

  async function loadHistory(conversationId: string) {
    try {
      const data = await fetch(`/api/chat/conversations/${encodeURIComponent(conversationId)}/history?limit=50`).then((r) => r.json())
      setHistory(data.messages || [])
    } catch {
      setHistory([])
    }
  }

  async function loadSimulationProducts() {
    setSimProductStatus('')
    try {
      const data = await fetchProducts({
        merchant_id: merchantId,
        platform: selectedPlatform,
        shop_id: currentSession?.shop_id || undefined,
        limit: 200,
      })
      const products = data.products || []
      setSimProducts(products)
      if (products.length === 0) {
        setSimProductStatus('当前平台还没有可用于模拟测试的商品')
      }
    } catch (error) {
      setSimProducts([])
      setSimProductStatus(error instanceof Error ? error.message : '商品列表读取失败')
    }
  }

  async function postAction(url: string, body: unknown, success: string) {
    setStatusText('')
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data?.detail?.message || data?.detail || data?.message || '请求失败')
      setStatusText(success)
      await loadData()
    } catch (error) {
      setStatusText(error instanceof Error ? error.message : '请求失败')
    }
  }

  function openChatPage() {
    postAction('/api/platform-browser/open', { platform: selectedPlatform, page_type: 'chat', headed: true }, '已打开客服页')
  }

  function openLoginPage() {
    postAction('/api/platform-browser/open', { platform: selectedPlatform, page_type: 'login', headed: true }, '已打开登录页，请在弹出的浏览器里完成登录后点击“检测登录”')
  }

  function checkLogin() {
    postAction('/api/platform-browser/check-login', { platform: selectedPlatform, page_type: 'chat' }, '已刷新登录状态')
  }

  function startAgent() {
    postAction(
      '/api/platform-browser/start-agent',
      { platform: selectedPlatform, page_type: 'chat', mode, interval_seconds: 8 },
      '已启动 AI 监听',
    )
  }

  function stopAgent() {
    postAction('/api/platform-browser/stop-agent', { agent_id: `${selectedPlatform}-chat` }, '已停止 AI 监听')
  }

  async function uploadCurrentConversation() {
    const transcript = buildTranscript(history)
    const content = learningDraft.trim() || transcript
    if (!content.trim()) {
      setUploadStatus('当前没有可导入内容')
      return
    }

      try {
        const formData = new FormData()
        formData.append('merchant_id', merchantId)
        formData.append('platform', selectedPlatform)
        if (currentSession?.shop_id) {
          formData.append('shop_id', currentSession.shop_id)
        }
        formData.append('files', new File([content], `quality-dialog-${Date.now()}.txt`, { type: 'text/plain' }))
        const result = await uploadKnowledge(formData)
      setUploadStatus(`已创建知识库任务：${result.upload_id}`)
    } catch (error) {
      setUploadStatus(error instanceof Error ? error.message : '上传失败')
    }
  }

  async function runSimulation() {
    const question = simQuestion.trim()
    if (!question) return
    setSimLoading(true)
    setSimAnswer('')
    setSimEvidence([])
    try {
      const result = await fetchChatResponse({
        merchant_id: merchantId,
        user_query: question,
        page_context: {
          platform: selectedPlatform,
          shop_id: currentSession?.shop_id || undefined,
          product_id: selectedSimProduct?.id || undefined,
          platform_product_id: selectedSimProduct?.platform_product_id || undefined,
          sku: selectedSimProduct?.sku || undefined,
          title: selectedSimProduct?.title || undefined,
          product_title: selectedSimProduct?.title || undefined,
          category: selectedSimProduct?.category || undefined,
          price: selectedSimProduct?.price ?? undefined,
          stock: selectedSimProduct?.stock ?? undefined,
          conversation_id: selectedConversationId || undefined,
          external_conversation_id: selectedConversation?.external_conversation_id || undefined,
          source: 'customer_service_simulation',
        },
      })
      setSimAnswer(result.response_text)
      setSimEvidence(result.evidence_sources || [])
    } catch (error) {
      setSimAnswer(error instanceof Error ? error.message : '模拟测试失败')
    } finally {
      setSimLoading(false)
    }
  }

  function toggleRule(ruleId: HandoffRuleKey) {
    setEnabledRules((current) =>
      current.includes(ruleId) ? current.filter((item) => item !== ruleId) : [...current, ruleId],
    )
  }

  async function saveRules() {
    const handoffRules = ruleOptions.reduce<Record<string, boolean>>((acc, rule) => {
      acc[rule.id] = enabledRules.includes(rule.id)
      return acc
    }, {})
    setRuleStatus('保存中...')
    try {
      const res = await fetch('/api/agent-rules', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          merchant_id: merchantId,
          platform: selectedPlatform,
          mode,
          auto_send_low_risk: mode === 'auto',
          confidence_threshold: confidenceThreshold,
          handoff_rules: handoffRules,
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data?.detail || data?.message || '保存规则失败')
      setRuleStatus('规则已保存，下一次 AI 决策会按新规则执行')
    } catch (error) {
      setRuleStatus(error instanceof Error ? error.message : '保存规则失败')
    }
  }

  async function copyRecommendedReply() {
    const text = String(agentMeta.recommended_reply || '')
    if (!text) {
      setStatusText('当前没有可复制的 AI 回复')
      return
    }
    await navigator.clipboard.writeText(text)
    setStatusText('已复制 AI 推荐回复')
  }

  async function handleResolveTicket(ticketId: string) {
    setStatusText('')
    try {
      await resolveHandoffTicket(ticketId)
      setStatusText('已标记为已处理')
      await loadData()
    } catch (error) {
      setStatusText(error instanceof Error ? error.message : '标记已处理失败')
    }
  }

  async function handleReturnToAi(ticketId: string) {
    setStatusText('')
    try {
      await returnHandoffTicketToAi(ticketId)
      setStatusText('已转回 AI 接待')
      // Also start the agent to resume AI listening
      await startAgent()
      await loadData()
    } catch (error) {
      setStatusText(error instanceof Error ? error.message : '转回 AI 失败')
    }
  }

  return (
    <div style={pageStyle}>
      <aside style={leftPanelStyle}>
        <div style={sectionHeaderStyle}>
          <Bot size={18} />
          <span>平台账号</span>
        </div>
        <div style={{ display: 'grid', gap: 8 }}>
          {platforms.map((platform) => {
            const session = sessions.find((item) => item.platform === platform.code && item.page_type === 'chat')
            const agent = agents.find((item) => item.platform === platform.code && item.status === 'running')
            const platSummary = handoffSummary?.platforms?.[platform.code]
            const hasPending = (platSummary?.pending || 0) > 0 || (platSummary?.processing || 0) > 0

            return (
              <button
                key={platform.code}
                onClick={() => setSelectedPlatform(platform.code)}
                style={{
                  ...accountButtonStyle,
                  background: selectedPlatform === platform.code ? '#eff6ff' : '#fff',
                  borderColor: selectedPlatform === platform.code ? '#93c5fd' : '#e5e7eb',
                  opacity: platform.status === 'coming_soon' ? 0.55 : 1,
                }}
              >
                <PlatformMark name={platform.name} color={platform.color} pending={hasPending} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <strong style={{ color: '#0f172a' }}>{platform.name}</strong>
                    {hasPending && <span style={dangerPillStyle}>待人工</span>}
                  </div>
                  <div style={mutedSmallStyle}>
                    {session?.logged_in ? '已登录' : '未登录'} · {agent ? '监听中' : session?.status || '未打开'}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </aside>

      <main style={mainStyle}>
        <header style={topBarStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <PlatformMark name={selectedPlatformDef?.name || '平台'} color={selectedPlatformDef?.color || '#2563eb'} />
              <div>
                <h1 style={{ margin: 0, fontSize: '1.25rem', color: '#0f172a' }}>{selectedPlatformDef?.name || selectedPlatform}</h1>
              <div style={mutedSmallStyle}>
                {selectedPlatformDef?.description || '多平台本地智能客服'} · {currentSession?.logged_in ? '已登录' : '未登录'} · {currentAgent?.status === 'running' ? '监听中' : currentSession?.status || '未打开'}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <select value={mode} onChange={(event) => setMode(event.target.value as AgentMode)} style={selectStyle}>
              <option value="dry_run">只记录不发送</option>
              <option value="assist">半托管填入</option>
              <option value="auto">低风险自动发送</option>
            </select>
            {!currentSession?.logged_in && (
              <IconButton icon={<LogIn size={15} />} label="打开登录页" onClick={openLoginPage} />
            )}
            <IconButton icon={<ExternalLink size={15} />} label="打开客服页" onClick={openChatPage} />
            <IconButton icon={<RefreshCw size={15} />} label="检测登录" onClick={checkLogin} />
            {currentAgent?.status === 'running' ? (
              <IconButton icon={<XCircle size={15} />} label="停止监听" onClick={stopAgent} tone="danger" />
            ) : (
              <IconButton icon={<PlayCircle size={15} />} label="启动 AI" onClick={startAgent} tone="primary" />
            )}
          </div>
        </header>

        {statusText && <div style={noticeStyle}>{statusText}</div>}
        {!currentSession?.logged_in && (
          <div style={warningNoticeStyle}>
            当前平台未检测到登录。先点“打开登录页”或“打开客服页”，在弹出的浏览器完成登录后，再点“检测登录”。
          </div>
        )}

        <section style={workspaceGridStyle}>
          <section style={panelStyle}>
            <div style={sectionHeaderStyle}>
              <ShieldAlert size={18} />
              <span>待人工处理</span>
              {pendingItems.length > 0 && <span style={dangerPillStyle}>{pendingItems.length}</span>}
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              {pendingItems.length === 0 ? (
                <EmptyState text="暂无待人工消息" />
              ) : (
                pendingItems.map((item) => (
                  <div key={item.id} style={handoffItemStyle}>
                    <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: 4 }}>{item.message}</div>
                    <div style={mutedSmallStyle}>原因：{item.reason}</div>
                    <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                      <button style={smallButtonStyle} onClick={() => handleResolveTicket(item.id)}>标记已处理</button>
                      <button style={smallPrimaryButtonStyle} onClick={() => handleReturnToAi(item.id)}>转回 AI 接待</button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>

          <section style={panelStyle}>
            <div style={sectionHeaderStyle}>
              <MessageSquare size={18} />
              <span>当前/历史会话</span>
            </div>
            <div style={conversationLayoutStyle}>
              <div style={conversationListStyle}>
                {conversations.length === 0 ? (
                  <EmptyState text="暂无本地会话记录" />
                ) : (
                  conversations.slice(0, 12).map((conversation) => (
                    <button
                      key={conversation.conversation_id}
                      onClick={() => setSelectedConversationId(conversation.conversation_id)}
                      style={{
                        ...conversationButtonStyle,
                        borderColor: selectedConversationId === conversation.conversation_id ? '#2563eb' : '#e5e7eb',
                        background: selectedConversationId === conversation.conversation_id ? '#eff6ff' : '#fff',
                      }}
                    >
                      <strong>{conversation.customer_name || conversation.external_conversation_id || conversation.conversation_id.slice(0, 10)}</strong>
                      <span style={mutedSmallStyle}>
                        {conversation.message_count || 0} 条 · {formatDate(conversation.last_updated)}
                      </span>
                    </button>
                  ))
                )}
              </div>
              <div style={messagePaneStyle}>
                <div style={{ marginBottom: 10 }}>
                  <strong>{selectedConversation?.customer_name || '会话详情'}</strong>
                  <div style={mutedSmallStyle}>{selectedConversation?.conversation_id || '选择一条会话查看历史'}</div>
                </div>
                <div style={messageListStyle}>
                  {history.length === 0 ? (
                    <EmptyState text="没有可展示的历史消息" />
                  ) : (
                    history.map((message, index) => <MessageBubble key={index} message={message} />)
                  )}
                </div>
              </div>
            </div>
          </section>

          <aside style={{ ...panelStyle, minHeight: 0 }}>
            <div style={sectionHeaderStyle}>
              <BrainCircuit size={18} />
              <span>AI 推荐回复</span>
            </div>
            <div style={{ display: 'grid', gap: 12 }}>
              <InfoRow label="最新买家消息" value={currentAgent?.latest_buyer_message || '等待新消息'} />
              <div>
                <div style={labelStyle}>推荐回复</div>
                <div style={replyBoxStyle}>{agentMeta.recommended_reply || 'AI 处理后会固定显示在这里，不会因为心跳刷新消失。'}</div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <span style={agentMeta.auto_send_allowed ? okPillStyle : dangerPillStyle}>
                  {agentMeta.auto_send_allowed ? '允许自动发送' : '需人工确认'}
                </span>
                <span style={neutralPillStyle}>置信度 {formatPercent(agentMeta.confidence)}</span>
                <span style={neutralPillStyle}>风险 {agentMeta.risk_level || '-'}</span>
              </div>
              {agentMeta.auto_send_blockers?.length > 0 && (
                <div style={{ color: '#b91c1c', fontSize: '0.8rem' }}>阻止原因：{formatBlockers(agentMeta.auto_send_blockers)}</div>
              )}
              <EvidencePanel evidence={(agentMeta.evidence_sources || []) as EvidenceSource[]} />
              <div style={{ display: 'flex', gap: 8 }}>
                <button style={smallButtonStyle} onClick={copyRecommendedReply}>复制回复</button>
                <button style={smallPrimaryButtonStyle} onClick={startAgent}>人工发送后转回 AI</button>
              </div>
            </div>
          </aside>
        </section>

        <section style={panelStyle}>
          <div style={tabBarStyle}>
            <TabButton icon={<ShieldAlert size={15} />} label="转人工规则" active={activeTab === 'rules'} onClick={() => setActiveTab('rules')} />
            <TabButton icon={<Upload size={15} />} label="对话学习" active={activeTab === 'learning'} onClick={() => setActiveTab('learning')} />
            <TabButton icon={<Send size={15} />} label="模拟测试" active={activeTab === 'simulation'} onClick={() => setActiveTab('simulation')} />
            <TabButton icon={<Clock size={15} />} label="处理记录" active={activeTab === 'handoff'} onClick={() => setActiveTab('handoff')} />
          </div>

          {activeTab === 'rules' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#334155', fontSize: '0.85rem', fontWeight: 700 }}>
                  低置信阈值
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    value={confidenceThreshold}
                    onChange={(event) => setConfidenceThreshold(Number(event.target.value))}
                    style={{ width: 86, border: '1px solid #e5e7eb', borderRadius: 6, padding: '6px 8px' }}
                  />
                </label>
                <button style={smallPrimaryButtonStyle} onClick={saveRules}>保存规则</button>
                {ruleStatus && <span style={mutedSmallStyle}>{ruleStatus}</span>}
              </div>
              <div style={ruleGridStyle}>
                {ruleOptions.map((rule) => (
                  <button
                    key={rule.id}
                    onClick={() => toggleRule(rule.id)}
                    style={{
                      ...ruleButtonStyle,
                      borderColor: enabledRules.includes(rule.id) ? '#2563eb' : '#e5e7eb',
                      background: enabledRules.includes(rule.id) ? '#eff6ff' : '#fff',
                    }}
                  >
                    <CheckCircle2 size={18} color={enabledRules.includes(rule.id) ? '#2563eb' : '#cbd5e1'} />
                    <div>
                      <strong>{rule.label}</strong>
                      <div style={mutedSmallStyle}>{rule.detail}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'learning' && (
            <div style={learningGridStyle}>
              <div>
                <div style={labelStyle}>从当前历史生成知识草稿</div>
                <textarea
                  value={learningDraft}
                  onChange={(event) => setLearningDraft(event.target.value)}
                  placeholder="可以粘贴曾经的优质对话，也可以先选择上方历史会话后直接导入。建议格式：买家问题 / 标准回答 / 适用商品 / 注意事项。"
                  style={textareaStyle}
                />
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button style={smallButtonStyle} onClick={() => setLearningDraft(buildTranscript(history))}>填入当前会话</button>
                  <button style={smallPrimaryButtonStyle} onClick={uploadCurrentConversation}>上传到知识库</button>
                </div>
                {uploadStatus && <div style={{ ...mutedSmallStyle, marginTop: 8 }}>{uploadStatus}</div>}
              </div>
              <div style={hintBoxStyle}>
                <strong>建议导入方式</strong>
                <p>先抓取平台历史对话，再删掉无效寒暄和错误回复，只保留“买家问法 + 优质回答 + 商品/售后约束”。这样比直接把整段聊天塞进知识库更稳定。</p>
              </div>
            </div>
          )}

          {activeTab === 'simulation' && (
            <div style={learningGridStyle}>
              <div>
                <div style={labelStyle}>模拟买家问题</div>
                <select
                  value={selectedSimProductId}
                  onChange={(event) => setSelectedSimProductId(event.target.value)}
                  style={{ ...selectStyle, width: '100%', marginBottom: 8 }}
                >
                  <option value="">不限定商品，只按当前平台/店铺知识库回答</option>
                  {simProducts.map((product) => (
                    <option key={product.id} value={product.id}>
                      {formatProductOption(product)}
                    </option>
                  ))}
                </select>
                {simProductStatus && <div style={{ ...mutedSmallStyle, marginBottom: 8 }}>{simProductStatus}</div>}
                {selectedSimProduct && (
                  <div style={{ ...hintBoxStyle, marginBottom: 10 }}>
                    <strong>{selectedSimProduct.title}</strong>
                    <div style={mutedSmallStyle}>
                      {[selectedSimProduct.platform, selectedSimProduct.shop_id, selectedSimProduct.platform_product_id || selectedSimProduct.sku]
                        .filter(Boolean)
                        .join(' / ') || '-'}
                    </div>
                    <div style={mutedSmallStyle}>
                      价格：{selectedSimProduct.price ?? '-'} · 库存：{selectedSimProduct.stock ?? '-'} · 类目：{selectedSimProduct.category || '-'}
                    </div>
                  </div>
                )}
                <textarea value={simQuestion} onChange={(event) => setSimQuestion(event.target.value)} style={{ ...textareaStyle, minHeight: 96 }} />
                <button style={{ ...smallPrimaryButtonStyle, marginTop: 8 }} onClick={runSimulation} disabled={simLoading}>
                  {simLoading ? '测试中...' : '测试 AI 回复'}
                </button>
              </div>
              <div>
                <div style={labelStyle}>AI 测试结果</div>
                <div style={simResultStyle}>{simAnswer || '测试结果会显示在这里。'}</div>
                <div style={{ marginTop: 10 }}>
                  <EvidencePanel evidence={simEvidence} compact={false} />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'handoff' && (
            <div style={resultGridStyle}>
              {handoffTickets.length === 0 ? (
                <EmptyState text="暂无处理记录" />
              ) : (
                handoffTickets.slice(0, 12).map((ticket) => (
                  <div key={ticket.ticket_id} style={resultItemStyle}>
                    <div style={{ fontWeight: 700 }}>{ticket.customer_message || '买家消息未记录'}</div>
                    {ticket.human_reply && <div style={{ color: '#047857', marginTop: 4 }}>已回复：{ticket.human_reply}</div>}
                    <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                      <span style={statusPillStyle(ticket.status)}>{ticket.status}</span>
                      <span style={mutedSmallStyle}>{ticket.reason || '-'}</span>
                    </div>
                    <div style={mutedSmallStyle}>{formatDate(ticket.created_at)}</div>
                  </div>
                ))
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

function PlatformMark({ name, color, pending = false }: { name: string; color: string; pending?: boolean }) {
  return (
    <div style={{ position: 'relative', width: 42, height: 42, flexShrink: 0 }}>
      <div style={{ width: 42, height: 42, borderRadius: 8, background: color, color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 800 }}>
        {name.charAt(0)}
      </div>
      {pending && <span style={{ position: 'absolute', right: -2, top: -2, width: 10, height: 10, borderRadius: 999, background: '#ef4444', border: '2px solid #fff' }} />}
    </div>
  )
}

function IconButton({ icon, label, onClick, tone }: { icon: ReactNode; label: string; onClick: () => void; tone?: 'primary' | 'danger' }) {
  return (
    <button
      onClick={onClick}
      style={{
        ...buttonStyle,
        background: tone === 'primary' ? '#2563eb' : tone === 'danger' ? '#dc2626' : '#fff',
        color: tone ? '#fff' : '#334155',
        borderColor: tone ? 'transparent' : '#e5e7eb',
      }}
    >
      {icon}
      {label}
    </button>
  )
}

function TabButton({ icon, label, active, onClick }: { icon: ReactNode; label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{ ...tabButtonStyle, background: active ? '#eff6ff' : '#fff', color: active ? '#1d4ed8' : '#475569', borderColor: active ? '#93c5fd' : '#e5e7eb' }}>
      {icon}
      {label}
    </button>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={labelStyle}>{label}</div>
      <div style={{ color: '#0f172a', lineHeight: 1.5 }}>{value}</div>
    </div>
  )
}

function EvidencePanel({ evidence, compact = true }: { evidence?: EvidenceSource[]; compact?: boolean }) {
  const items = (evidence || []).filter(Boolean).slice(0, compact ? 4 : 8)
  return (
    <div>
      <div style={labelStyle}>知识来源</div>
      {items.length === 0 ? (
        <div style={mutedSmallStyle}>暂无明确来源</div>
      ) : (
        <div style={{ display: 'grid', gap: 6 }}>
          {items.map((item, index) => (
            <div key={`${item.type || 'source'}-${index}`} style={evidenceItemStyle}>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={neutralPillStyle}>{formatEvidenceType(item.type)}</span>
                {item.score != null && <span style={neutralPillStyle}>{formatPercent(item.score)}</span>}
              </div>
              <div style={{ fontWeight: 700, color: '#0f172a', marginTop: 4 }}>
                {item.title || item.source || 'unknown'}
              </div>
              <div style={mutedSmallStyle}>
                {[item.platform, item.shop_id, item.product_id, item.sku].filter(Boolean).join(' / ') || item.source || '-'}
              </div>
              {item.preview && <div style={evidencePreviewStyle}>{item.preview}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function MessageBubble({ message }: { message: HistoryMessage }) {
  const role = message.role || 'unknown'
  const isBuyer = role === 'user' || role === 'buyer'
  const content = message.content || message.text || ''
  const evidence = getMessageEvidence(message)
  return (
    <div style={{ ...bubbleStyle, alignSelf: isBuyer ? 'flex-start' : 'flex-end', background: isBuyer ? '#fff' : '#ecfdf5', borderColor: isBuyer ? '#e5e7eb' : '#bbf7d0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        {isBuyer ? <UserRound size={14} /> : <Bot size={14} />}
        <strong>{isBuyer ? '买家' : role === 'assistant_sent' ? '已发送' : 'AI'}</strong>
      </div>
      <div>{content || '-'}</div>
      {!isBuyer && evidence.length > 0 && (
        <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid #d1fae5' }}>
          <EvidencePanel evidence={evidence} />
        </div>
      )}
    </div>
  )
}

function EmptyState({ text }: { text: string }) {
  return <div style={{ color: '#94a3b8', fontSize: '0.85rem', padding: '1rem', textAlign: 'center' }}>{text}</div>
}

function buildTranscript(history: HistoryMessage[]) {
  return history
    .map((item) => {
      const role = item.role === 'user' || item.role === 'buyer' ? '买家' : '客服/AI'
      return `${role}: ${item.content || item.text || ''}`
    })
    .filter((line) => line.trim().length > 4)
    .join('\n')
}

function formatBlockers(value: unknown) {
  return Array.isArray(value) ? value.join('、') : String(value || '')
}

function formatPercent(value: unknown) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return `${Math.round(num * 100)}%`
}

function formatEvidenceType(value?: string) {
  switch (value) {
    case 'rag_chunk':
      return 'RAG'
    case 'structured_data':
      return '结构化'
    case 'product_recommendation':
      return '推荐'
    default:
      return value || '来源'
  }
}

function getMessageEvidence(message: HistoryMessage): EvidenceSource[] {
  const rawEvidence = message.metadata?.evidence_sources
  if (!Array.isArray(rawEvidence)) return []
  return rawEvidence.filter(
    (item): item is EvidenceSource => Boolean(item) && typeof item === 'object' && !Array.isArray(item),
  )
}

function statusPillStyle(status: string): CSSProperties {
  const base: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    borderRadius: 999,
    padding: '2px 8px',
    fontSize: '0.72rem',
    fontWeight: 800,
  }
  switch (status) {
    case 'pending':
      return { ...base, background: '#fef2f2', color: '#dc2626' }
    case 'processing':
      return { ...base, background: '#fffbeb', color: '#d97706' }
    case 'resolved':
      return { ...base, background: '#dcfce7', color: '#15803d' }
    case 'returned_to_ai':
      return { ...base, background: '#eff6ff', color: '#2563eb' }
    case 'closed':
      return { ...base, background: '#f1f5f9', color: '#64748b' }
    default:
      return { ...base, background: '#f1f5f9', color: '#475569' }
  }
}

function formatProductOption(product: ProductSummary) {
  const parts = [
    product.title,
    product.price != null ? `¥${product.price}` : null,
    product.stock != null ? `库存${product.stock}` : null,
    product.platform_product_id || product.sku || null,
  ].filter(Boolean)
  return parts.join(' · ')
}

function formatDate(value?: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const pageStyle: CSSProperties = {
  minHeight: '100vh',
  display: 'grid',
  gridTemplateColumns: '280px minmax(0, 1fr)',
  gap: 16,
  padding: '1rem 1.5rem',
  background: '#eef2f7',
}

const leftPanelStyle: CSSProperties = {
  background: '#fff',
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: 14,
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
  minHeight: 0,
}

const mainStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
  minWidth: 0,
}

const topBarStyle: CSSProperties = {
  background: '#fff',
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: '14px 16px',
  display: 'flex',
  justifyContent: 'space-between',
  gap: 12,
  alignItems: 'center',
}

const workspaceGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: '300px minmax(0, 1fr) 340px',
  gap: 12,
  minHeight: 430,
}

const panelStyle: CSSProperties = {
  background: '#fff',
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: 14,
  boxShadow: '0 1px 2px rgba(15,23,42,0.04)',
}

const sectionHeaderStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  marginBottom: 12,
  fontWeight: 800,
  color: '#0f172a',
}

const accountButtonStyle: CSSProperties = {
  width: '100%',
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: 10,
  display: 'flex',
  gap: 10,
  alignItems: 'center',
  textAlign: 'left',
  cursor: 'pointer',
}

const buttonStyle: CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 6,
  height: 36,
  padding: '0 12px',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  cursor: 'pointer',
  fontWeight: 700,
}

const selectStyle: CSSProperties = {
  height: 36,
  border: '1px solid #e5e7eb',
  borderRadius: 6,
  padding: '0 10px',
  background: '#fff',
  color: '#334155',
}

const noticeStyle: CSSProperties = {
  border: '1px solid #bfdbfe',
  background: '#eff6ff',
  color: '#1d4ed8',
  borderRadius: 8,
  padding: '10px 12px',
  fontSize: '0.85rem',
}

const warningNoticeStyle: CSSProperties = {
  border: '1px solid #fde68a',
  background: '#fffbeb',
  color: '#92400e',
  borderRadius: 8,
  padding: '10px 12px',
  fontSize: '0.85rem',
}

const mutedSmallStyle: CSSProperties = {
  color: '#64748b',
  fontSize: '0.78rem',
}

const dangerPillStyle: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  borderRadius: 999,
  padding: '2px 8px',
  background: '#fef2f2',
  color: '#dc2626',
  fontSize: '0.72rem',
  fontWeight: 800,
}

const okPillStyle: CSSProperties = {
  ...dangerPillStyle,
  background: '#dcfce7',
  color: '#15803d',
}

const neutralPillStyle: CSSProperties = {
  ...dangerPillStyle,
  background: '#f1f5f9',
  color: '#475569',
}

const evidenceItemStyle: CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: 8,
  background: '#fff',
  fontSize: '0.78rem',
}

const evidencePreviewStyle: CSSProperties = {
  marginTop: 6,
  color: '#334155',
  lineHeight: 1.45,
  maxHeight: 72,
  overflow: 'hidden',
  whiteSpace: 'pre-wrap',
}

const handoffItemStyle: CSSProperties = {
  border: '1px solid #fde68a',
  background: '#fffbeb',
  borderRadius: 8,
  padding: 10,
}

const smallButtonStyle: CSSProperties = {
  border: '1px solid #e5e7eb',
  background: '#fff',
  color: '#334155',
  borderRadius: 6,
  padding: '7px 10px',
  cursor: 'pointer',
  fontWeight: 700,
}

const smallPrimaryButtonStyle: CSSProperties = {
  ...smallButtonStyle,
  borderColor: '#2563eb',
  background: '#2563eb',
  color: '#fff',
}

const conversationLayoutStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: '220px minmax(0, 1fr)',
  gap: 10,
  minHeight: 360,
}

const conversationListStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  overflowY: 'auto',
}

const conversationButtonStyle: CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: 10,
  background: '#fff',
  textAlign: 'left',
  display: 'grid',
  gap: 4,
  cursor: 'pointer',
}

const messagePaneStyle: CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: 12,
  minWidth: 0,
}

const messageListStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  maxHeight: 300,
  overflowY: 'auto',
}

const bubbleStyle: CSSProperties = {
  maxWidth: '78%',
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: '8px 10px',
  color: '#0f172a',
  lineHeight: 1.5,
  fontSize: '0.85rem',
}

const labelStyle: CSSProperties = {
  color: '#64748b',
  fontSize: '0.78rem',
  marginBottom: 5,
  fontWeight: 700,
}

const replyBoxStyle: CSSProperties = {
  minHeight: 110,
  border: '1px solid #bbf7d0',
  background: '#f0fdf4',
  borderRadius: 8,
  padding: 12,
  lineHeight: 1.6,
  color: '#0f172a',
  whiteSpace: 'pre-wrap',
}

const tabBarStyle: CSSProperties = {
  display: 'flex',
  gap: 8,
  marginBottom: 12,
  flexWrap: 'wrap',
}

const tabButtonStyle: CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 6,
  background: '#fff',
  padding: '7px 12px',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  cursor: 'pointer',
  fontWeight: 800,
}

const ruleGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
  gap: 10,
}

const ruleButtonStyle: CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  background: '#fff',
  padding: 12,
  display: 'flex',
  gap: 10,
  textAlign: 'left',
  cursor: 'pointer',
}

const learningGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'minmax(0, 1fr) 360px',
  gap: 14,
}

const textareaStyle: CSSProperties = {
  width: '100%',
  minHeight: 170,
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: 10,
  resize: 'vertical',
  lineHeight: 1.5,
  color: '#0f172a',
  boxSizing: 'border-box',
}

const hintBoxStyle: CSSProperties = {
  border: '1px solid #fde68a',
  background: '#fffbeb',
  borderRadius: 8,
  padding: 12,
  color: '#92400e',
  lineHeight: 1.6,
}

const simResultStyle: CSSProperties = {
  minHeight: 170,
  border: '1px solid #bbf7d0',
  background: '#f0fdf4',
  borderRadius: 8,
  padding: 12,
  whiteSpace: 'pre-wrap',
  lineHeight: 1.6,
}

const resultGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
  gap: 10,
}

const resultItemStyle: CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: 10,
  background: '#fff',
  fontSize: '0.85rem',
}

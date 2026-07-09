import { useEffect, useState, useRef } from 'react'
import {
  Bot,
  ChevronRight,
  ExternalLink,
  Eye,
  Globe,
  Loader2,
  MessageSquare,
  RefreshCw,
  Shield,
  XCircle,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PlatformDef {
  code: string
  name: string
  icon: string
  color: string
  status: 'active' | 'beta' | 'coming_soon'
  description: string
}

interface BrowserSession {
  session_id: string
  platform: string
  page_type: string
  profile_id: string
  status: string
  logged_in: boolean
  current_url: string | null
  page_title: string | null
  last_heartbeat_at: string | null
  error_message: string | null
  target_after_login: string | null
}

interface AgentInfo {
  agent_id: string
  platform: string
  status: string
  latest_buyer_message?: string | null
  selector_profile?: string | null
  current_page_url?: string | null
  metadata?: Record<string, unknown> | null
}

interface SendResultInfo {
  id?: string
  platform?: string
  customer_message?: string | null
  sent_text?: string | null
  send_status?: string | null
  processing_status?: string | null
  created_at?: string | null
}

// ---------------------------------------------------------------------------
// PlatformIcon
// ---------------------------------------------------------------------------

function PlatformIcon({ name, color, size = 36 }: { name: string; color: string; size?: number }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 10,
        backgroundColor: color,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
        fontWeight: 700,
        fontSize: size * 0.4,
        flexShrink: 0,
      }}
    >
      {name.charAt(0)}
    </div>
  )
}

// ---------------------------------------------------------------------------
// StatusBadge
// ---------------------------------------------------------------------------

function StatusBadge({ status, label }: { status: string; label?: string }) {
  const config: Record<string, { label: string; color: string; bg: string }> = {
    not_opened: { label: '未打开', color: '#94a3b8', bg: '#f1f5f9' },
    opening: { label: '打开中', color: '#2563eb', bg: '#eff6ff' },
    login_required: { label: '需登录', color: '#ca8a04', bg: '#fef3c7' },
    ready: { label: '已就绪', color: '#16a34a', bg: '#dcfce7' },
    running: { label: '监听中', color: '#16a34a', bg: '#dcfce7' },
    paused: { label: '已暂停', color: '#64748b', bg: '#f1f5f9' },
    error: { label: '异常', color: '#dc2626', bg: '#fef2f2' },
  }
  const c = config[status] || { label: label || status, color: '#64748b', bg: '#f1f5f9' }
  return (
    <span style={{ fontSize: '0.7rem', padding: '2px 10px', borderRadius: 999, backgroundColor: c.bg, color: c.color, fontWeight: 600 }}>
      {c.label}
    </span>
  )
}

function RiskBadge({ level }: { level?: string }) {
  const config: Record<string, { label: string; color: string; bg: string }> = {
    low: { label: '低风险', color: '#16a34a', bg: '#dcfce7' },
    medium: { label: '中风险', color: '#ca8a04', bg: '#fef3c7' },
    high: { label: '高风险', color: '#dc2626', bg: '#fef2f2' },
  }
  const c = config[level || ''] || { label: level || '未知', color: '#64748b', bg: '#f1f5f9' }
  return (
    <span style={{ fontSize: '0.7rem', padding: '2px 10px', borderRadius: 999, backgroundColor: c.bg, color: c.color, fontWeight: 600 }}>
      {c.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function PlatformBrowserWorkbench() {
  const [platformList, setPlatformList] = useState<PlatformDef[]>([])
  const [sessions, setSessions] = useState<BrowserSession[]>([])
  const [onlineAgents, setOnlineAgents] = useState<AgentInfo[]>([])
  const [sendResults, setSendResults] = useState<SendResultInfo[]>([])
  const [selectedPlatform, setSelectedPlatform] = useState<string>('pinduoduo')
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<'dry_run' | 'assist' | 'auto'>('dry_run')
  const [activePageType, setActivePageType] = useState<string>('chat')
  const [fetchError, setFetchError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadData = async () => {
    try {
      const [platformRes, sessionRes, agentRes] = await Promise.all([
        fetch('/api/platform/list').then(r => r.json()),
        fetch('/api/platform-browser/sessions').then(r => r.json()),
        fetch('/api/local-agent/status').then(r => r.json()),
      ])
      setPlatformList((platformRes.platforms || []).filter((p: PlatformDef) => p.status !== 'coming_soon' || true))
      setSessions(sessionRes.sessions || [])
      setOnlineAgents((agentRes.agents || []).filter((a: AgentInfo) => a.status === 'running'))
      const activePlatform = selectedPlatform
      try {
        const statusRes = await fetch(`/api/platform/${activePlatform}/status`).then(r => r.json())
        setSendResults(statusRes.recent_send_results || [])
      } catch {
        setSendResults([])
      }
    } catch {
      // ignore polling errors
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    intervalRef.current = setInterval(loadData, 5000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [selectedPlatform])

  const currentSession = sessions.find(s => s.platform === selectedPlatform && s.page_type === activePageType)
  const currentPlatform = platformList.find(p => p.code === selectedPlatform)
  const currentAgent = onlineAgents.find(a => a.agent_id === `${selectedPlatform}-${activePageType}`)
    || onlineAgents.find(a => a.platform === selectedPlatform)
  const agentMeta: Record<string, any> | undefined = currentAgent?.metadata as Record<string, any> | undefined

  const apiCall = async (url: string, body: unknown, label: string): Promise<boolean> => {
    setFetchError(null)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) {
        const msg = data?.detail?.message || data?.detail || data?.message || `${label}失败`
        setFetchError(`${label}失败：${msg}`)
        return false
      }
      return true
    } catch (err) {
      setFetchError(`${label}失败：无法连接到后端服务`)
      return false
    }
  }

  const handleOpenPage = async (pageType: string) => {
    setActivePageType(pageType)
    const ok = await apiCall('/api/platform-browser/open', { platform: selectedPlatform, page_type: pageType, headed: true }, `打开${pageType === 'login' ? '登录页' : pageType === 'chat' ? '客服页' : '商品页'}`)
    if (ok) loadData()
  }

  const handleCheckLogin = async () => {
    const ok = await apiCall('/api/platform-browser/check-login', { platform: selectedPlatform, page_type: activePageType }, '检测登录')
    if (ok) loadData()
  }

  const handleStartAgent = async () => {
    const ok = await apiCall('/api/platform-browser/start-agent', {
      platform: selectedPlatform,
      page_type: activePageType,
      mode,
      interval_seconds: 10,
    }, '启动 AI 接待')
    if (ok) loadData()
  }

  const handleStopAgent = async () => {
    const agentId = `${selectedPlatform}-${activePageType}`
    const ok = await apiCall('/api/platform-browser/stop-agent', { agent_id: agentId }, '停止监听')
    if (ok) loadData()
  }

  const handleFocus = async () => {
    await apiCall('/api/platform-browser/focus', { platform: selectedPlatform, page_type: activePageType }, '聚焦窗口')
  }

  const handleRefresh = async () => {
    await apiCall('/api/platform-browser/refresh', { platform: selectedPlatform, page_type: activePageType }, '刷新页面')
  }

  const handleClose = async () => {
    const ok = await apiCall('/api/platform-browser/close', { platform: selectedPlatform, page_type: activePageType }, '关闭页面')
    if (ok) loadData()
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 2rem)', padding: '1rem 1.5rem', gap: 16 }}>
      {/* ===== Left: Platform List ===== */}
      <aside
        style={{
          width: 260,
          flexShrink: 0,
          background: '#fff',
          borderRadius: 12,
          boxShadow: '0 1px 3px rgba(15,23,42,0.08)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '1rem', borderBottom: '1px solid #f1f5f9' }}>
          <h2 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Bot size={18} />
            平台账号
          </h2>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
          {platformList.map(p => {
            const sess = sessions.find(s => s.platform === p.code)
            const agent = onlineAgents.find(a => a.platform === p.code)
            const isSelected = selectedPlatform === p.code
            const sessionStatus = sess?.status || 'not_opened'
            const meta = agent?.metadata as Record<string, any> | undefined
            const hasPending = Boolean(agent?.latest_buyer_message && meta?.auto_send_allowed !== true)
            return (
              <button
                key={p.code}
                onClick={() => setSelectedPlatform(p.code)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '0.75rem',
                  borderRadius: 8,
                  border: 'none',
                  background: isSelected ? '#f1f5f9' : 'transparent',
                  cursor: 'pointer',
                  marginBottom: 4,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  opacity: p.status === 'coming_soon' ? 0.5 : 1,
                }}
              >
                <div style={{ position: 'relative', flexShrink: 0 }}>
                  <PlatformIcon name={p.name} color={p.color} size={36} />
                  {hasPending && (
                    <span style={{
                      position: 'absolute', right: -2, top: -2, width: 10, height: 10,
                      borderRadius: 999, background: '#ef4444', border: '2px solid #fff',
                    }} />
                  )}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#0f172a', display: 'flex', alignItems: 'center', gap: 6 }}>
                    {p.name}
                    {p.status === 'coming_soon' && (
                      <span style={{ fontSize: '0.65rem', color: '#ca8a04', background: '#fef3c7', padding: '1px 6px', borderRadius: 4 }}>待接入</span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                    <StatusBadge status={p.status === 'coming_soon' ? 'not_opened' : sessionStatus} />
                    {agent && <span style={{ fontSize: '0.65rem', color: '#16a34a' }}>监听中</span>}
                    {hasPending && <span style={{ fontSize: '0.65rem', color: '#dc2626' }}>待处理</span>}
                  </div>
                </div>
                {isSelected && <ChevronRight size={16} color="#94a3b8" />}
              </button>
            )
          })}
        </div>
        <div style={{ padding: '0.75rem 1rem', borderTop: '1px solid #f1f5f9', fontSize: '0.7rem', color: '#94a3b8' }}>
          <button onClick={loadData} style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 4 }}>
            <RefreshCw size={12} /> 刷新状态
          </button>
        </div>
      </aside>

      {/* ===== Right: Workspace ===== */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, overflow: 'auto' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
            <Loader2 size={24} className="animate-spin" />
          </div>
        ) : !currentPlatform ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', flexDirection: 'column', gap: 12 }}>
            <Bot size={48} opacity={0.3} />
            <div style={{ fontSize: '1rem' }}>选择一个平台开始使用</div>
          </div>
        ) : (
          <>
            {/* ===== Error Banner ===== */}
            {fetchError && (
              <div style={{ padding: '10px 14px', borderRadius: 8, background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <XCircle size={16} />
                <span style={{ flex: 1 }}>{fetchError}</span>
                <button onClick={() => setFetchError(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#991b1b', fontSize: '0.85rem' }}>✕</button>
              </div>
            )}

            {/* ===== Platform Header ===== */}
            <div
              style={{
                background: '#fff',
                borderRadius: 10,
                padding: '1rem 1.25rem',
                boxShadow: '0 1px 3px rgba(15,23,42,0.08)',
                display: 'flex',
                alignItems: 'center',
                gap: 14,
              }}
            >
              <PlatformIcon name={currentPlatform.name} color={currentPlatform.color} size={48} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <h1 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: '#0f172a' }}>{currentPlatform.name}</h1>
                  <StatusBadge status={currentSession?.status || 'not_opened'} />
                  {currentSession?.logged_in && <StatusBadge status="ready" />}
                </div>
                <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 2 }}>{currentPlatform.description}</div>
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <select
                  value={mode}
                  onChange={e => setMode(e.target.value as 'dry_run' | 'assist' | 'auto')}
                  style={{
                    padding: '6px 10px',
                    border: '1px solid #e2e8f0',
                    borderRadius: 6,
                    fontSize: '0.8rem',
                    color: '#334155',
                    background: '#fff',
                  }}
                >
                  <option value="dry_run">Dry-Run</option>
                  <option value="assist">半托管</option>
                  <option value="auto">全托管</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 12, flex: 1 }}>
              {/* ===== Left Column: Controls + Monitor ===== */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* Connection Control */}
                <div style={{ background: '#fff', borderRadius: 10, padding: '1rem', boxShadow: '0 1px 3px rgba(15,23,42,0.08)' }}>
                  <h3 style={{ margin: '0 0 10px', fontSize: '0.85rem', color: '#334155', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Globe size={16} /> 平台连接
                    <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 400 }}>（当前页：{activePageType === 'login' ? '登录页' : activePageType === 'chat' ? '客服页' : activePageType === 'products' ? '商品页' : activePageType}）</span>
                  </h3>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button onClick={() => handleOpenPage('login')} style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                      <ExternalLink size={14} /> 打开登录页
                    </button>
                    <button onClick={() => handleOpenPage('chat')} style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                      <ExternalLink size={14} /> 打开客服页
                    </button>
                    <button onClick={() => handleOpenPage('products')} style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                      <ExternalLink size={14} /> 打开商品页
                    </button>
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                    <button onClick={handleCheckLogin} style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                      <RefreshCw size={14} /> 检测登录
                    </button>
                    <button onClick={handleFocus} style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                      <Eye size={14} /> 聚焦窗口
                    </button>
                    <button onClick={handleRefresh} style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                      <RefreshCw size={14} /> 刷新
                    </button>
                    <button onClick={handleClose} style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                      <XCircle size={14} /> 关闭
                    </button>
                  </div>
                  <div style={{ marginTop: 10, fontSize: '0.75rem', color: '#64748b', wordBreak: 'break-all' }}>
                    <span style={{ color: '#94a3b8' }}>状态：</span>
                    {currentSession?.logged_in ? '✅ 已登录' : '❌ 未登录'}
                    <span style={{ margin: '0 8px', color: '#d1d5db' }}>|</span>
                    {currentSession?.current_url ? (
                      <><span style={{ color: '#94a3b8' }}>URL：</span>{currentSession.current_url}</>
                    ) : (
                      <span style={{ color: '#94a3b8' }}>页面未打开</span>
                    )}
                  </div>
                  {currentSession?.target_after_login && (
                    <div style={{ marginTop: 4, fontSize: '0.75rem', color: '#ca8a04' }}>
                      登录后将自动跳转到：{currentSession.target_after_login === 'chat' ? '客服页' : currentSession.target_after_login === 'products' ? '商品页' : currentSession.target_after_login}
                    </div>
                  )}
                  {currentSession?.error_message && (
                    <div style={{ marginTop: 4, fontSize: '0.75rem', color: '#dc2626' }}>
                      错误：{currentSession.error_message}
                    </div>
                  )}
                </div>

                {/* Agent Control */}
                <div style={{ background: '#fff', borderRadius: 10, padding: '1rem', boxShadow: '0 1px 3px rgba(15,23,42,0.08)' }}>
                  <h3 style={{ margin: '0 0 10px', fontSize: '0.85rem', color: '#334155', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Bot size={16} /> AI 接待
                  </h3>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {currentSession?.status === 'running' ? (
                      <button onClick={handleStopAgent} style={{ padding: '6px 14px', borderRadius: 6, border: 'none', background: '#dc2626', color: '#fff', cursor: 'pointer', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                        <XCircle size={14} /> 停止监听
                      </button>
                    ) : (
                      <button
                        onClick={handleStartAgent}
                        disabled={!currentSession?.logged_in}
                        style={{
                          padding: '6px 14px',
                          borderRadius: 6,
                          border: 'none',
                          background: currentSession?.logged_in ? '#2563eb' : '#e2e8f0',
                          color: currentSession?.logged_in ? '#fff' : '#94a3b8',
                          cursor: currentSession?.logged_in ? 'pointer' : 'not-allowed',
                          fontSize: '0.8rem',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 5,
                        }}
                      >
                        <Eye size={14} /> 启动 AI 接待
                      </button>
                    )}
                  </div>
                  <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Shield size={14} color={mode === 'dry_run' ? '#8b5cf6' : '#dc2626'} />
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      {mode === 'dry_run' ? 'Dry-Run：只记录不回填' : mode === 'assist' ? '半托管：回填输入框，不自动发送' : '全托管：低风险自动发送'}
                    </span>
                  </div>
                </div>

                {/* Live Monitor: Buyer Message + AI Decision */}
                <div style={{ background: '#fff', borderRadius: 10, padding: '1rem', boxShadow: '0 1px 3px rgba(15,23,42,0.08)', flex: 1 }}>
                  <h3 style={{ margin: '0 0 10px', fontSize: '0.85rem', color: '#334155', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <MessageSquare size={16} /> 实时监控
                  </h3>

                  <div style={{ display: 'grid', gap: 10 }}>
                    {/* Buyer message */}
                    <div>
                      <div>最新买家消息</div>
                      <div>{String(currentAgent?.latest_buyer_message ?? '等待新消息…')}</div>
                    </div>

                    {/* Product context */}
                    {(agentMeta?.product_name || agentMeta?.sku) && (
                      <div>
                        <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>商品上下文</div>
                        <div style={{ fontSize: '0.8rem', color: '#334155' }}>
                          {String(agentMeta?.product_name || '') && <span style={{ fontWeight: 600 }}>{String(agentMeta?.product_name || '')}</span>}
                          {String(agentMeta?.sku || '') && <span style={{ marginLeft: 8, color: '#64748b' }}>SKU: {String(agentMeta?.sku || '')}</span>}
                          {String(agentMeta?.product_price || '') && <span style={{ marginLeft: 8, color: '#64748b' }}>¥{String(agentMeta?.product_price || '')}</span>}
                        </div>
                      </div>
                    )}

                    {/* AI Decision */}
                    {agentMeta?.recommended_reply ? (
                      <div>
                        <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>AI 推荐回复</div>
                        <div style={{ fontSize: '0.8rem', color: '#0f172a', background: '#f0fdf4', padding: '8px 10px', borderRadius: 6, lineHeight: 1.5 }}>
                          {String(agentMeta?.recommended_reply || '')}
                        </div>
                        <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                          <RiskBadge level={String(agentMeta?.risk_level || '')} />
                          {agentMeta?.auto_send_allowed
                            ? <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 999, background: '#dcfce7', color: '#16a34a', fontWeight: 600 }}>允许自动发送</span>
                            : <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 999, background: '#fef2f2', color: '#dc2626', fontWeight: 600 }}>禁止自动发送</span>
                          }
                          {Array.isArray(agentMeta?.auto_send_blockers) && (agentMeta.auto_send_blockers as string[]).length > 0 && (
                            <span style={{ fontSize: '0.7rem', color: '#dc2626' }}>
                              阻止: {(agentMeta.auto_send_blockers as string[]).join(', ')}
                            </span>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>暂无 AI 决策数据</div>
                    )}

                    {sendResults.length > 0 && (
                      <div>
                        <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>最近处理记录</div>
                        <div style={{ display: 'grid', gap: 6 }}>
                          {sendResults.slice(-5).reverse().map((item, index) => (
                            <div key={item.id || index} style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: '8px 10px', fontSize: '0.78rem', color: '#334155', background: '#fff' }}>
                              <div style={{ fontWeight: 600 }}>{item.customer_message || '-'}</div>
                              {item.sent_text && <div style={{ marginTop: 4, color: '#047857' }}>{item.sent_text}</div>}
                              <div style={{ marginTop: 4, color: '#94a3b8' }}>{item.send_status || item.processing_status || '-'}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* ===== Right Column: Details ===== */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* Session Info */}
                <div style={{ background: '#fff', borderRadius: 10, padding: '1rem', boxShadow: '0 1px 3px rgba(15,23,42,0.08)' }}>
                  <h3 style={{ margin: '0 0 8px', fontSize: '0.85rem', color: '#334155' }}>会话详情</h3>
                  <div style={{ fontSize: '0.78rem', color: '#64748b', display: 'grid', gap: 6 }}>
                    <div><span style={{ color: '#94a3b8' }}>状态：</span>{currentSession?.status || 'not_opened'}</div>
                    <div><span style={{ color: '#94a3b8' }}>登录：</span>{currentSession?.logged_in ? '✅ 已登录' : '❌ 未登录'}</div>
                    <div><span style={{ color: '#94a3b8' }}>Profile：</span>{currentSession?.profile_id || '-'}</div>
                    {currentSession?.last_heartbeat_at && (
                      <div><span style={{ color: '#94a3b8' }}>最近心跳：</span>{new Date(currentSession.last_heartbeat_at).toLocaleString('zh-CN')}</div>
                    )}
                  </div>
                </div>

                {/* AI Decision Detail */}
                <div style={{ background: '#fff', borderRadius: 10, padding: '1rem', boxShadow: '0 1px 3px rgba(15,23,42,0.08)' }}>
                  <h3 style={{ margin: '0 0 8px', fontSize: '0.85rem', color: '#334155' }}>AI 决策详情</h3>
                  {agentMeta ? (
                    <div style={{ fontSize: '0.78rem', color: '#64748b', display: 'grid', gap: 5 }}>
                      <div><span style={{ color: '#94a3b8' }}>意图：</span>{String(agentMeta?.intent || '-')}</div>
                      <div><span style={{ color: '#94a3b8' }}>置信度：</span>{agentMeta?.confidence != null ? `${Math.round(Number(agentMeta.confidence) * 100)}%` : '-'}</div>
                      <div><span style={{ color: '#94a3b8' }}>发送状态：</span>{String(agentMeta?.send_status || '-')}</div>
                      <div><span style={{ color: '#94a3b8' }}>转人工：</span>{agentMeta?.handoff_required ? '需要' : '不需要'}</div>
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>暂无决策</div>
                  )}
                </div>

                {/* Tips */}
                <div style={{ background: '#f8fafc', borderRadius: 10, padding: '1rem', fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.6 }}>
                  <strong style={{ color: '#64748b' }}>操作提示</strong>
                  <ul style={{ margin: '6px 0 0', paddingLeft: 16 }}>
                    <li>点击"打开客服页"启动浏览器</li>
                    <li>在浏览器中完成平台登录</li>
                    <li>返回后点击"检测登录"确认</li>
                    <li>选择接待模式后启动 AI</li>
                    <li>手动回复直接在浏览器窗口操作</li>
                  </ul>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  )
}

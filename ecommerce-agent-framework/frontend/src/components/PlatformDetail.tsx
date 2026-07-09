import { useEffect, useState, useRef } from 'react'
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  ExternalLink,
  Eye,
  MessageSquare,
  RefreshCw,
  Shield,
  ToggleLeft,
  ToggleRight,
  XCircle,
} from 'lucide-react'
import type { AgentInfo, AgentMetadata } from '../services/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SendResult {
  id: string
  send_status: string
  processing_status: string
  customer_message: string | null
  sent_text: string | null
  created_at: string
  decision: Record<string, unknown> | null
}

interface PlatformStatus {
  platform: {
    code: string
    name: string
    color: string
    description: string
  }
  agents: AgentInfo[]
  agent_count: number
  recent_send_results: SendResult[]
  send_result_count: number
}

interface PlatformDetailProps {
  platformCode: string
  onBack: () => void
}

// ---------------------------------------------------------------------------
// Helper Components
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; color: string; bg: string }> = {
    running: { label: '运行中', color: '#16a34a', bg: '#dcfce7' },
    paused: { label: '已暂停', color: '#ca8a04', bg: '#fef9c3' },
    stopped: { label: '已停止', color: '#64748b', bg: '#f1f5f9' },
    error: { label: '异常', color: '#dc2626', bg: '#fef2f2' },
  }
  const c = config[status] || { label: status, color: '#64748b', bg: '#f1f5f9' }
  return (
    <span style={{ fontSize: '0.75rem', padding: '2px 10px', borderRadius: 999, backgroundColor: c.bg, color: c.color, fontWeight: 600 }}>
      {c.label}
    </span>
  )
}

function SendResultBadge({ status }: { status: string }) {
  const colors: Record<string, { label: string; color: string }> = {
    success: { label: '成功', color: '#16a34a' },
    auto_sent: { label: '自动发送', color: '#16a34a' },
    handoff: { label: '转人工', color: '#ca8a04' },
    handoff_required: { label: '转人工', color: '#ca8a04' },
    skipped_dry_run: { label: 'Dry-Run', color: '#2563eb' },
    failed: { label: '失败', color: '#dc2626' },
  }
  const c = colors[status] || { label: status, color: '#64748b' }
  return (
    <span style={{ fontSize: '0.7rem', padding: '1px 8px', borderRadius: 999, backgroundColor: c.color + '15', color: c.color, fontWeight: 500 }}>
      {c.label}
    </span>
  )
}

function RiskBadge({ level }: { level?: string }) {
  const config: Record<string, { label: string; color: string; bg: string }> = {
    low: { label: '低风险', color: '#16a34a', bg: '#dcfce7' },
    medium: { label: '中风险', color: '#ca8a04', bg: '#fef9c3' },
    high: { label: '高风险', color: '#dc2626', bg: '#fef2f2' },
  }
  const c = config[level || ''] || { label: level || '未知', color: '#64748b', bg: '#f1f5f9' }
  return (
    <span style={{ fontSize: '0.7rem', padding: '2px 10px', borderRadius: 999, backgroundColor: c.bg, color: c.color, fontWeight: 600 }}>
      {c.label}
    </span>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: '#fff', borderRadius: 10, boxShadow: '0 1px 3px rgba(15,23,42,0.08)', overflow: 'hidden' }}>
      <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid #f1f5f9', fontWeight: 600, fontSize: '0.8rem', color: '#334155' }}>
        {title}
      </div>
      <div style={{ padding: '0.75rem 1rem' }}>
        {children}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function PlatformDetail({ platformCode, onBack }: PlatformDetailProps) {
  const [data, setData] = useState<PlatformStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dryRunMode, setDryRunMode] = useState(true)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadData = () => {
    setLoading(true)
    fetch(`/api/platform/${platformCode}/status`)
      .then((res) => res.json())
      .then((d) => {
        if (d.error) {
          setError(d.message)
        } else {
          setData(d)
          setError(null)
        }
      })
      .catch(() => setError('无法连接到后端服务'))
      .finally(() => setLoading(false))
  }

  // Initial load + auto-poll every 5s
  useEffect(() => {
    loadData()
    intervalRef.current = setInterval(loadData, 5000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [platformCode])

  const platformName = data?.platform?.name || platformCode
  const platformColor = data?.platform?.color || '#2563eb'

  // Derive the "primary" running agent for live monitor display
  const runningAgents = data?.agents.filter((a) => a.status === 'running') || []
  const primaryAgent: AgentInfo | undefined = runningAgents[0]
  const agentMeta: AgentMetadata | undefined = primaryAgent?.metadata as AgentMetadata | undefined

  return (
    <div style={{ padding: '1.5rem 2rem', maxWidth: '1200px' }}>
      {/* ===== Header ===== */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <button onClick={onBack} style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.5rem', cursor: 'pointer', display: 'flex', alignItems: 'center', color: '#64748b' }}>
          <ArrowLeft size={18} />
        </button>
        <div style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: platformColor, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '1.2rem', fontWeight: 700 }}>
          {platformName.charAt(0)}
        </div>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{platformName} 工作台</h1>
          <p style={{ fontSize: '0.8rem', color: '#64748b' }}>{data?.platform?.description || ''}</p>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 4 }}>
          <Clock size={12} />
          每 5 秒自动刷新
        </div>
        <button onClick={loadData} disabled={loading} style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.5rem 1rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, color: '#64748b', fontSize: '0.875rem' }}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          刷新
        </button>
      </div>

      {/* ===== Error Banner ===== */}
      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '1rem', color: '#991b1b', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {loading && !data && (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#94a3b8' }}>加载中...</div>
      )}

      {data && (
        <>
          {/* ===== Stat Cards ===== */}
          <div style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', marginBottom: 12 }}>运行状态</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
              {[
                { label: 'Agent 数量', value: data.agent_count, icon: <Activity size={20} />, color: '#2563eb' },
                { label: '最近发送结果', value: data.send_result_count, icon: <MessageSquare size={20} />, color: '#16a34a' },
                { label: '运行中', value: data.agents.filter((a) => a.status === 'running').length, icon: <Clock size={20} />, color: '#ca8a04' },
                { label: '安全模式', value: dryRunMode ? 'Dry-Run' : '允许发送', icon: <Shield size={20} />, color: dryRunMode ? '#8b5cf6' : '#dc2626' },
              ].map((stat) => (
                <div key={stat.label} style={{ background: '#fff', borderRadius: 10, padding: '1rem', boxShadow: '0 1px 3px rgba(15,23,42,0.08)', display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, backgroundColor: stat.color + '15', color: stat.color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {stat.icon}
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{stat.label}</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a' }}>{stat.value}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ===== Live Monitor (only when an agent is running) ===== */}
          {primaryAgent && (
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', marginBottom: 12 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Eye size={16} /> 会话监控
                  <span style={{ fontSize: '0.7rem', fontWeight: 400, color: '#94a3b8' }}>
                    — 来自 {primaryAgent.agent_id}
                  </span>
                </span>
              </h2>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                {/* Left column: Buyer Message + Product Context */}
                <Card title="买家消息">
                  {primaryAgent.latest_buyer_message ? (
                    <div>
                      <div style={{ fontSize: '0.9rem', color: '#0f172a', marginBottom: 4 }}>
                        {primaryAgent.latest_buyer_message}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
                        {primaryAgent.last_message_seen_at
                          ? `收到时间: ${new Date(primaryAgent.last_message_seen_at).toLocaleString('zh-CN')}`
                          : ''}
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Clock size={14} /> 等待新消息...
                    </div>
                  )}
                </Card>

                {/* Product Context */}
                <Card title="商品上下文">
                  {agentMeta?.product_name ? (
                    <div style={{ fontSize: '0.8rem', color: '#334155' }}>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>{agentMeta.product_name}</div>
                      <div style={{ color: '#64748b' }}>
                        {agentMeta.sku && <span>SKU: {agentMeta.sku}</span>}
                        {agentMeta.product_price && <span style={{ marginLeft: 12 }}>价格: ¥{agentMeta.product_price}</span>}
                        {agentMeta.stock !== undefined && <span style={{ marginLeft: 12 }}>库存: {agentMeta.stock}</span>}
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>暂无商品上下文</div>
                  )}
                </Card>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                {/* AI Decision */}
                <Card title="AI 决策">
                  {agentMeta?.recommended_reply ? (
                    <div>
                      <div style={{ marginBottom: 8 }}>
                        <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>推荐回复</div>
                        <div style={{ fontSize: '0.8rem', color: '#0f172a', background: '#f8fafc', padding: '8px 10px', borderRadius: 6, lineHeight: 1.4 }}>
                          {agentMeta.recommended_reply}
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
                        <RiskBadge level={agentMeta.risk_level} />
                        {agentMeta.auto_send_allowed
                          ? <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 999, backgroundColor: '#dcfce7', color: '#16a34a', fontWeight: 600 }}>允许自动发送</span>
                          : <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 999, backgroundColor: '#fef2f2', color: '#dc2626', fontWeight: 600 }}>禁止自动发送</span>
                        }
                        {agentMeta.intent && <span style={{ fontSize: '0.7rem', color: '#64748b' }}>意图: {agentMeta.intent}</span>}
                        {agentMeta.confidence !== undefined && <span style={{ fontSize: '0.7rem', color: '#64748b' }}>置信度: {(agentMeta.confidence * 100).toFixed(0)}%</span>}
                      </div>
                      {agentMeta.auto_send_blockers && agentMeta.auto_send_blockers.length > 0 && (
                        <div style={{ marginTop: 8, fontSize: '0.75rem', color: '#dc2626', display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                          {agentMeta.auto_send_blockers.map((b, i) => (
                            <span key={i} style={{ padding: '1px 6px', background: '#fef2f2', borderRadius: 4 }}>{b}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>尚无 AI 决策</div>
                  )}
                </Card>

                {/* Selector Profile + Page URL */}
                <Card title="监控配置">
                  {primaryAgent.selector_profile ? (
                    <div>
                      <div style={{ marginBottom: 8 }}>
                        <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>选择器 Profile</span>
                        <div style={{ marginTop: 2 }}>
                          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#334155' }}>{primaryAgent.selector_profile}</span>
                          <span style={{ fontSize: '0.7rem', marginLeft: 8, padding: '1px 6px', borderRadius: 4, background: '#eff6ff', color: '#2563eb' }}>local</span>
                        </div>
                      </div>
                      {primaryAgent.current_page_url && (
                        <div>
                          <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>监控页面</span>
                          <div style={{ fontSize: '0.75rem', color: '#64748b', wordBreak: 'break-all', marginTop: 2 }}>
                            {primaryAgent.current_page_url}
                          </div>
                        </div>
                      )}
                      <div style={{ marginTop: 8 }}>
                        <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>窗口标题</span>
                        <div style={{ fontSize: '0.8rem', color: '#334155', marginTop: 2 }}>
                          {primaryAgent.watched_window_title || '-'}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>暂无配置信息</div>
                  )}
                </Card>
              </div>
            </div>
          )}

          {/* ===== Mode Control ===== */}
          <div style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', marginBottom: 12 }}>安全控制</h2>
            <div style={{ background: '#fff', borderRadius: 10, padding: '1.25rem', boxShadow: '0 1px 3px rgba(15,23,42,0.08)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <Shield size={20} color={dryRunMode ? '#8b5cf6' : '#dc2626'} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: '#0f172a', fontSize: '0.9rem' }}>
                    {dryRunMode ? 'Dry-Run 模式（安全）' : '允许真实发送'}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                    {dryRunMode
                      ? 'AI 生成回复但不回填输入框，不点击发送按钮'
                      : 'AI 可在低风险且证据充分时真实发送到客服页面'}
                  </div>
                </div>
                <button
                  onClick={() => setDryRunMode(!dryRunMode)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: dryRunMode ? '#8b5cf6' : '#dc2626', display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.875rem' }}
                >
                  {dryRunMode ? <ToggleRight size={28} /> : <ToggleLeft size={28} />}
                  <span style={{ fontWeight: 600 }}>{dryRunMode ? 'Dry-Run' : '允许发送'}</span>
                </button>
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', borderTop: '1px solid #f1f5f9', paddingTop: 8, marginTop: 4 }}>
                注意：切换为"允许真实发送"后，请确认当前会话安全。命令行参数 <code style={{ background: '#f1f5f9', padding: '1px 4px', borderRadius: 2 }}>--allow-real-send</code> 仍作为底层保险。
              </div>
            </div>
          </div>

          {/* ===== Agent Detail Cards ===== */}
          {data.agents.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', marginBottom: 12 }}>Agent 详情</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {data.agents.map((agent) => (
                  <AgentCard key={agent.agent_id} agent={agent} />
                ))}
              </div>
            </div>
          )}

          {data.agents.length === 0 && (
            <div style={{ background: '#fff', borderRadius: 10, padding: '2rem', textAlign: 'center', color: '#94a3b8', marginBottom: 24, boxShadow: '0 1px 3px rgba(15,23,42,0.08)' }}>
              <Clock size={36} style={{ marginBottom: 8, opacity: 0.4 }} />
              <div>尚无 Agent 运行</div>
              <div style={{ fontSize: '0.8rem', marginTop: 4 }}>启动 Local Agent 后，这里将显示运行状态和心跳信息</div>
            </div>
          )}

          {/* ===== Recent Send Results ===== */}
          {data.recent_send_results.length > 0 && (
            <div>
              <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', marginBottom: 12 }}>最近发送记录</h2>
              <div style={{ background: '#fff', borderRadius: 10, boxShadow: '0 1px 3px rgba(15,23,42,0.08)', overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', textAlign: 'left', color: '#64748b' }}>
                      <th style={{ padding: '10px 16px' }}>买家消息</th>
                      <th style={{ padding: '10px 16px' }}>回复内容</th>
                      <th style={{ padding: '10px 16px' }}>发送状态</th>
                      <th style={{ padding: '10px 16px' }}>处理结果</th>
                      <th style={{ padding: '10px 16px' }}>时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_send_results.map((r) => (
                      <tr key={r.id} style={{ borderTop: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '10px 16px', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {r.customer_message || '-'}
                        </td>
                        <td style={{ padding: '10px 16px', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {r.sent_text || '-'}
                        </td>
                        <td style={{ padding: '10px 16px' }}>
                          {r.send_status === 'success' ? (
                            <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#16a34a' }}>
                              <CheckCircle2 size={14} /> 成功
                            </span>
                          ) : r.send_status === 'failed' ? (
                            <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#dc2626' }}>
                              <XCircle size={14} /> 失败
                            </span>
                          ) : (
                            <span style={{ color: '#64748b' }}>{r.send_status}</span>
                          )}
                        </td>
                        <td style={{ padding: '10px 16px' }}>
                          <SendResultBadge status={r.processing_status} />
                        </td>
                        <td style={{ padding: '10px 16px', color: '#94a3b8', whiteSpace: 'nowrap' }}>
                          {r.created_at ? new Date(r.created_at).toLocaleString('zh-CN') : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ===== How to Start Local Agent ===== */}
          <div style={{ marginTop: 24 }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', marginBottom: 12 }}>启动方式</h2>
            <div style={{ background: '#1e293b', borderRadius: 10, padding: '1rem', fontSize: '0.8rem', fontFamily: 'monospace', color: '#e2e8f0', overflowX: 'auto' }}>
              <div style={{ color: '#94a3b8', marginBottom: 8 }}>
                # 在终端中运行以下命令启动 Local Agent（Dry-Run 模式）：
              </div>
              <div style={{ lineHeight: 1.8 }}>
                cd D:/develop_python/system/ecommerce-agent-framework<br />
                $env:DEBUG='false'<br />
                D:/anaconda3/python.exe -m app.local_agent.run_browser_mock `<br />
                --watch --interval 15 `<br />
                --user-data-dir data/browser_profiles/pdd_edge
              </div>
              <div style={{ color: '#fbbf24', marginTop: 8 }}>
                # 安全提示：默认不真实发送，加 --allow-real-send 才允许自动回复
              </div>
            </div>
          </div>

          {/* ===== Info Footer ===== */}
          <div style={{ marginTop: 16, padding: '1rem', background: '#f8fafc', borderRadius: 8, fontSize: '0.75rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 8 }}>
            <ExternalLink size={14} />
            {primaryAgent?.current_page_url ? (
              <>
                监控页面：
                <code style={{ background: '#f1f5f9', padding: '2px 6px', borderRadius: 4, fontSize: '0.75rem' }}>
                  {primaryAgent.current_page_url}
                </code>
              </>
            ) : (
              <>
                平台工作台地址：
                <code style={{ background: '#f1f5f9', padding: '2px 6px', borderRadius: 4, fontSize: '0.75rem' }}>
                  {data?.platform?.description || platformCode}
                </code>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Agent Card Sub-component
// ---------------------------------------------------------------------------

function AgentCard({ agent }: { agent: AgentInfo }) {
  const meta = agent.metadata as AgentMetadata | undefined

  return (
    <div style={{ background: '#fff', borderRadius: 10, padding: '1.25rem', boxShadow: '0 1px 3px rgba(15,23,42,0.08)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: agent.status === 'running' ? '#16a34a' : agent.status === 'error' ? '#dc2626' : '#94a3b8' }} />
        <span style={{ fontWeight: 600, color: '#0f172a', fontSize: '0.9rem' }}>{agent.agent_id}</span>
        <StatusBadge status={agent.status} />
        {agent.selector_profile && (
          <span style={{ fontSize: '0.7rem', padding: '1px 8px', borderRadius: 4, background: '#eff6ff', color: '#2563eb', marginLeft: 4 }}>{agent.selector_profile}</span>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8, fontSize: '0.8rem', color: '#64748b' }}>
        <div><span style={{ color: '#94a3b8' }}>平台:</span> {agent.platform || '-'}</div>
        <div><span style={{ color: '#94a3b8' }}>店铺:</span> {agent.shop_id || '-'}</div>
        <div><span style={{ color: '#94a3b8' }}>窗口:</span> {agent.watched_window_title || '-'}</div>
        <div><span style={{ color: '#94a3b8' }}>最近心跳:</span> {agent.last_heartbeat_at ? new Date(agent.last_heartbeat_at).toLocaleString('zh-CN') : '-'}</div>
        <div><span style={{ color: '#94a3b8' }}>最近消息:</span> {agent.last_message_seen_at ? new Date(agent.last_message_seen_at).toLocaleString('zh-CN') : '-'}</div>
        <div><span style={{ color: '#94a3b8' }}>最近发送:</span> {agent.last_send_at ? new Date(agent.last_send_at).toLocaleString('zh-CN') : '-'}</div>
        {agent.latest_buyer_message && (
          <div style={{ gridColumn: '1 / -1' }}>
            <span style={{ color: '#94a3b8' }}>最新买家消息:</span>{' '}
            <span style={{ color: '#334155' }}>{agent.latest_buyer_message}</span>
          </div>
        )}
        {meta?.recommended_reply && (
          <div style={{ gridColumn: '1 / -1' }}>
            <span style={{ color: '#94a3b8' }}>推荐回复:</span>{' '}
            <span style={{ color: '#334155' }}>{meta.recommended_reply}</span>
          </div>
        )}
      </div>

      {agent.error_message && (
        <div style={{ marginTop: 10, padding: '8px 12px', background: '#fef2f2', borderRadius: 6, fontSize: '0.8rem', color: '#991b1b', display: 'flex', alignItems: 'center', gap: 6 }}>
          <AlertCircle size={14} />
          {agent.error_message}
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import { Sliders, ToggleLeft, ToggleRight, HelpCircle } from 'lucide-react'

const MODES = [
  {
    id: 'auto',
    title: 'AI 全托管',
    description: '低风险问题自动回复，中高风险问题自动转人工',
    details: [
      '低风险且证据充分时自动发送',
      '中高风险直接转人工',
      '无证据不编造',
      '适合售前咨询、明确商品和政策问题',
    ],
  },
  {
    id: 'collaboration',
    title: '人机协作',
    description: 'AI 生成推荐回复，人工审核后发送',
    details: [
      '默认不自动发送',
      '低风险可配置为自动发送',
      '所有中高风险进入人工待处理',
      '适合刚开始试用的阶段',
    ],
  },
  {
    id: 'smart',
    title: '智能转接',
    description: 'AI 处理常规问题，复杂问题转给指定人工',
    details: [
      'AI 处理常规咨询',
      '命中转接规则时生成摘要和处理建议',
      '可配置转接原因和目标账号',
      '适合多客服团队',
    ],
  },
]

export default function ReplyStrategy() {
  const [selectedMode, setSelectedMode] = useState('collaboration')
  const [autoSend, setAutoSend] = useState(false)

  return (
    <div style={{ padding: '1.5rem 2rem', maxWidth: '1200px' }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a', marginBottom: 4 }}>AI 回复策略</h1>
      <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: 24 }}>
        选择 AI 接待模式和自动发送规则
      </p>

      {/* Mode Selection */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
        {MODES.map((mode) => (
          <div
            key={mode.id}
            onClick={() => setSelectedMode(mode.id)}
            style={{
              background: '#fff',
              borderRadius: 10,
              padding: '1.25rem',
              boxShadow: '0 1px 3px rgba(15,23,42,0.08)',
              border: `2px solid ${selectedMode === mode.id ? '#2563eb' : '#f1f5f9'}`,
              cursor: 'pointer',
              transition: 'border-color 0.15s',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
              <div
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: '50%',
                  border: `2px solid ${selectedMode === mode.id ? '#2563eb' : '#d1d5db'}`,
                  backgroundColor: selectedMode === mode.id ? '#2563eb' : 'transparent',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginTop: 2,
                  flexShrink: 0,
                }}
              >
                {selectedMode === mode.id && (
                  <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#fff' }} />
                )}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, color: '#0f172a', marginBottom: 4 }}>{mode.title}</div>
                <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: 8 }}>
                  {mode.description}
                </div>
                <ul style={{ fontSize: '0.75rem', color: '#94a3b8', paddingLeft: 16, margin: 0 }}>
                  {mode.details.map((d, i) => (
                    <li key={i} style={{ marginBottom: 2 }}>
                      {d}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Auto-send Toggle */}
      <div
        style={{
          background: '#fff',
          borderRadius: 10,
          padding: '1.25rem',
          boxShadow: '0 1px 3px rgba(15,23,42,0.08)',
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <Sliders size={20} color="#64748b" />
          <span style={{ fontWeight: 600, color: '#0f172a' }}>低风险自动发送</span>
          <div style={{ flex: 1 }} />
          <button
            onClick={() => setAutoSend(!autoSend)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: autoSend ? '#16a34a' : '#94a3b8',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: '0.875rem',
            }}
          >
            {autoSend ? <ToggleRight size={28} /> : <ToggleLeft size={28} />}
            <span>{autoSend ? '已开启' : '已关闭'}</span>
          </button>
        </div>
        <div style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6 }}>
          <HelpCircle size={14} />
          开启后，低风险问题将由 AI 自动回复，无需人工确认
        </div>
      </div>

      {/* Config hint */}
      <div
        style={{
          padding: '1rem',
          background: '#f8fafc',
          borderRadius: 8,
          fontSize: '0.8rem',
          color: '#64748b',
        }}
      >
        转人工触发项配置（关键词、图片消息、售后风险、超出知识库等）将在后续版本中提供。
      </div>
    </div>
  )
}

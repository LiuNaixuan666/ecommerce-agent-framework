import { useEffect, useState } from 'react'
import { Clock, Activity, Zap, AlertCircle, ChevronRight } from 'lucide-react'

interface PlatformCard {
  code: string
  name: string
  icon: string
  color: string
  order: number
  status: 'active' | 'beta' | 'coming_soon'
  description: string
  agent_count: number
  running_count: number
  error_count: number
  has_active_agent: boolean
  latest_heartbeat_at: string | null
}

interface DashboardProps {
  onNavigateToPlatform: (platformCode: string) => void
}

// Platform icon component — uses colored circles with initials
function PlatformLogo({ name, color, status }: { name: string; color: string; status: string }) {
  const initial = name.charAt(0)
  return (
    <div
      style={{
        width: 56,
        height: 56,
        borderRadius: 14,
        backgroundColor: status === 'coming_soon' ? '#e2e8f0' : color,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
        fontSize: '1.5rem',
        fontWeight: 700,
        opacity: status === 'coming_soon' ? 0.5 : 1,
        flexShrink: 0,
      }}
    >
      {initial}
    </div>
  )
}

export default function Dashboard({ onNavigateToPlatform }: DashboardProps) {
  const [platforms, setPlatforms] = useState<PlatformCard[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/platform/list')
      .then((res) => res.json())
      .then((data) => {
        setPlatforms(data.platforms || [])
      })
      .catch(() => {
        // Fallback if backend not running
        setPlatforms([])
      })
      .finally(() => setLoading(false))
  }, [])

  const activePlatforms = platforms.filter((p) => p.status !== 'coming_soon')
  const comingSoonPlatforms = platforms.filter((p) => p.status === 'coming_soon')

  const totalRunning = activePlatforms.reduce((sum, p) => sum + p.running_count, 0)
  const totalErrors = activePlatforms.reduce((sum, p) => sum + p.error_count, 0)

  return (
    <div style={{ padding: '1.5rem 2rem', maxWidth: '1200px' }}>
      {/* Page Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>综合工作台</h1>
        <p style={{ fontSize: '0.875rem', color: '#64748b', marginTop: 4 }}>
          多平台 AI 客服统一管理，当前已接入 {activePlatforms.length} 个平台
        </p>
      </div>

      {/* Stats Overview */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 16,
          marginBottom: 24,
        }}
      >
        {[
          { label: '运行中 Agent', value: totalRunning, icon: <Zap size={18} />, color: '#16a34a' },
          { label: '接入平台数', value: activePlatforms.length, icon: <Activity size={18} />, color: '#2563eb' },
          { label: '异常 Agent', value: totalErrors, icon: <AlertCircle size={18} />, color: totalErrors > 0 ? '#dc2626' : '#94a3b8' },
          { label: '待接入平台', value: comingSoonPlatforms.length, icon: <Clock size={18} />, color: '#ca8a04' },
        ].map((stat) => (
          <div
            key={stat.label}
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: '1rem 1.25rem',
              boxShadow: '0 1px 3px rgba(15,23,42,0.08)',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                backgroundColor: stat.color + '15',
                color: stat.color,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {stat.icon}
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{stat.label}</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{stat.value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Active Platforms */}
      {activePlatforms.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', marginBottom: 12 }}>已接入平台</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {activePlatforms.map((platform) => (
              <PlatformCard
                key={platform.code}
                platform={platform}
                onClick={() => onNavigateToPlatform(platform.code)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Coming Soon Platforms */}
      {comingSoonPlatforms.length > 0 && (
        <div>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', marginBottom: 12 }}>待接入平台</h2>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: 12,
            }}
          >
            {comingSoonPlatforms.map((platform) => (
              <div
                key={platform.code}
                style={{
                  background: '#fff',
                  borderRadius: 12,
                  padding: '1.25rem',
                  boxShadow: '0 1px 3px rgba(15,23,42,0.08)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 16,
                  opacity: 0.7,
                  cursor: 'not-allowed',
                }}
              >
                <PlatformLogo name={platform.name} color={platform.color} status="coming_soon" />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: '#334155' }}>{platform.name}</div>
                  <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{platform.description}</div>
                </div>
                <div
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 8px',
                    borderRadius: 999,
                    backgroundColor: '#fef3c7',
                    color: '#92400e',
                    fontWeight: 500,
                  }}
                >
                  即将接入
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#94a3b8' }}>加载中...</div>
      )}
      {!loading && platforms.length === 0 && (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#94a3b8' }}>
          <AlertCircle size={40} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
          <div>无法加载平台信息，请确认后端已启动</div>
        </div>
      )}
    </div>
  )
}

function PlatformCard({ platform, onClick }: { platform: PlatformCard; onClick: () => void }) {
  const statusLabel = platform.running_count > 0 ? '运行中' : platform.error_count > 0 ? '异常' : '未启动'
  const statusColor = platform.running_count > 0 ? '#16a34a' : platform.error_count > 0 ? '#dc2626' : '#94a3b8'

  return (
    <div
      onClick={onClick}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '1.25rem',
        boxShadow: '0 1px 3px rgba(15,23,42,0.08)',
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        cursor: 'pointer',
        transition: 'box-shadow 0.2s, transform 0.15s',
        border: '1px solid #f1f5f9',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(15,23,42,0.12)'
        e.currentTarget.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(15,23,42,0.08)'
        e.currentTarget.style.transform = 'translateY(0)'
      }}
    >
      <PlatformLogo name={platform.name} color={platform.color} status={platform.status} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontWeight: 600, fontSize: '1rem', color: '#0f172a' }}>{platform.name}</span>
          <span
            style={{
              fontSize: '0.7rem',
              padding: '2px 8px',
              borderRadius: 999,
              backgroundColor: statusColor + '18',
              color: statusColor,
              fontWeight: 500,
            }}
          >
            {statusLabel}
          </span>
        </div>
        <div style={{ fontSize: '0.8rem', color: '#64748b' }}>{platform.description}</div>
        <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: '0.75rem', color: '#94a3b8' }}>
          <span>Agent: {platform.agent_count}</span>
          <span>运行中: {platform.running_count}</span>
          {platform.latest_heartbeat_at && (
            <span>最近心跳: {new Date(platform.latest_heartbeat_at).toLocaleString('zh-CN')}</span>
          )}
        </div>
      </div>
      <ChevronRight size={20} color="#94a3b8" />
    </div>
  )
}

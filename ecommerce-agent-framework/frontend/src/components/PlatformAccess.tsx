import { Smartphone } from 'lucide-react'

export default function PlatformAccess() {
  return (
    <div style={{ padding: '1.5rem 2rem', maxWidth: '1200px' }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a', marginBottom: 4 }}>平台接入</h1>
      <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: 24 }}>
        管理各电商平台的接入配置和浏览器自动化设置
      </p>

      {/* Platform list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div
          style={{
            background: '#fff',
            borderRadius: 10,
            padding: '1.25rem',
            boxShadow: '0 1px 3px rgba(15,23,42,0.08)',
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            border: '1px solid #e2e8f0',
          }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 10,
              backgroundColor: '#E02E24',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontWeight: 700,
              fontSize: '1.1rem',
            }}
          >
            拼
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, color: '#0f172a' }}>拼多多</div>
            <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
              浏览器 Profile: data/browser_profiles/pdd_edge
            </div>
          </div>
          <span
            style={{
              fontSize: '0.7rem',
              padding: '2px 10px',
              borderRadius: 999,
              backgroundColor: '#dcfce7',
              color: '#16a34a',
              fontWeight: 600,
            }}
          >
            已配置
          </span>
        </div>

        {['闲鱼', '淘宝 / 千牛', '京东', '抖店'].map((name) => (
          <div
            key={name}
            style={{
              background: '#fff',
              borderRadius: 10,
              padding: '1.25rem',
              boxShadow: '0 1px 3px rgba(15,23,42,0.08)',
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              opacity: 0.6,
            }}
          >
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 10,
                backgroundColor: '#e2e8f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#94a3b8',
                fontWeight: 700,
                fontSize: '1.1rem',
              }}
            >
              {name.charAt(0)}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, color: '#64748b' }}>{name}</div>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>尚未接入</div>
            </div>
            <span
              style={{
                fontSize: '0.7rem',
                padding: '2px 10px',
                borderRadius: 999,
                backgroundColor: '#f1f5f9',
                color: '#94a3b8',
                fontWeight: 500,
              }}
            >
              待接入
            </span>
          </div>
        ))}
      </div>

      {/* Config hint */}
      <div
        style={{
          marginTop: 24,
          padding: '1rem',
          background: '#f8fafc',
          borderRadius: 8,
          fontSize: '0.8rem',
          color: '#64748b',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <Smartphone size={16} />
        平台接入当前通过浏览器自动化实现，暂不依赖平台官方 API。
      </div>
    </div>
  )
}

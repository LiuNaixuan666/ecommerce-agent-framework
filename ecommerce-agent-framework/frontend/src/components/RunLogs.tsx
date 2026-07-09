import { ScrollText, Filter } from 'lucide-react'

export default function RunLogs() {
  return (
    <div style={{ padding: '1.5rem 2rem', maxWidth: '1200px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a', marginBottom: 4 }}>运行日志</h1>
          <p style={{ fontSize: '0.875rem', color: '#64748b' }}>
            Local Agent 运行日志和 AI 决策记录
          </p>
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '0.5rem 1rem',
            background: '#fff',
            borderRadius: 8,
            border: '1px solid #e2e8f0',
            color: '#64748b',
            fontSize: '0.8rem',
            cursor: 'pointer',
          }}
        >
          <Filter size={16} />
          筛选条件
        </div>
      </div>

      {/* Table placeholder */}
      <div
        style={{
          background: '#fff',
          borderRadius: 10,
          boxShadow: '0 1px 3px rgba(15,23,42,0.08)',
          overflow: 'hidden',
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
          <thead>
            <tr style={{ background: '#f8fafc', textAlign: 'left', color: '#64748b' }}>
              <th style={{ padding: '12px 16px' }}>时间</th>
              <th style={{ padding: '12px 16px' }}>平台</th>
              <th style={{ padding: '12px 16px' }}>Agent ID</th>
              <th style={{ padding: '12px 16px' }}>事件类型</th>
              <th style={{ padding: '12px 16px' }}>内容</th>
              <th style={{ padding: '12px 16px' }}>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderTop: '1px solid #f1f5f9' }}>
              <td style={{ padding: '12px 16px', color: '#94a3b8' }} colSpan={6} align="center">
                <div style={{ padding: '2rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                  <ScrollText size={36} style={{ opacity: 0.3 }} />
                  <div style={{ color: '#94a3b8' }}>暂无运行日志</div>
                  <div style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>
                    启动 Local Agent 后，运行记录将显示在这里
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

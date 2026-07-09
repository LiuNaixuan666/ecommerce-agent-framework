import { LayoutDashboard, ShoppingCart, MessageSquare, Bot, ScrollText, ChevronLeft, ChevronRight, MessageCircle, Package, Monitor } from 'lucide-react'

export type NavView = 'dashboard' | 'platform-detail' | 'chat' | 'mock' | 'platform-access' | 'reply-strategy' | 'run-logs' | 'products' | 'platform-workbench'

interface SidebarProps {
  currentView: NavView
  onNavigate: (view: NavView) => void
  collapsed: boolean
  onToggleCollapse: () => void
  platform?: string
}

const navItems: { view: NavView; label: string; icon: React.ReactNode }[] = [
  { view: 'dashboard', label: '综合工作台', icon: <LayoutDashboard size={20} /> },
  { view: 'platform-workbench', label: '客服工作台', icon: <Monitor size={20} /> },
  { view: 'platform-detail', label: '平台详情', icon: <ShoppingCart size={20} /> },
  { view: 'products', label: '商品管理', icon: <Package size={20} /> },
  { view: 'platform-access', label: '平台接入', icon: <Bot size={20} /> },
  { view: 'reply-strategy', label: 'AI 回复策略', icon: <MessageSquare size={20} /> },
  { view: 'run-logs', label: '运行日志', icon: <ScrollText size={20} /> },
]

const toolItems: { view: NavView; label: string; icon: React.ReactNode }[] = [
  { view: 'mock', label: 'Mock 工作台', icon: <MessageCircle size={20} /> },
  { view: 'chat', label: '知识库聊天', icon: <MessageSquare size={20} /> },
]

export default function Sidebar({ currentView, onNavigate, collapsed, onToggleCollapse }: SidebarProps) {
  return (
    <aside
      style={{
        width: collapsed ? 64 : 240,
        minHeight: '100vh',
        backgroundColor: '#1e293b',
        color: '#e2e8f0',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s ease',
        flexShrink: 0,
      }}
    >
      {/* Logo / Title */}
      <div
        style={{
          padding: collapsed ? '1rem 0' : '1rem 1.25rem',
          borderBottom: '1px solid #334155',
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          minHeight: 64,
        }}
      >
        {!collapsed && (
          <div>
            <div style={{ fontWeight: 700, fontSize: '1.05rem', color: '#f1f5f9' }}>AI 客服中台</div>
            <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: 2 }}>多平台本地智能客服</div>
          </div>
        )}
        {collapsed && (
          <div style={{ fontWeight: 700, fontSize: '1.1rem', color: '#f1f5f9' }}>AI</div>
        )}
        <button
          onClick={onToggleCollapse}
          style={{
            background: 'none',
            border: 'none',
            color: '#94a3b8',
            cursor: 'pointer',
            padding: 4,
            display: 'flex',
            alignItems: 'center',
            borderRadius: 4,
          }}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: '0.75rem 0' }}>
        {!collapsed && (
          <div style={{ padding: '0.5rem 1.25rem', fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            主功能
          </div>
        )}
        {navItems.map((item) => (
          <button
            key={item.view}
            onClick={() => onNavigate(item.view)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              width: '100%',
              padding: collapsed ? '0.75rem 0' : '0.6rem 1.25rem',
              border: 'none',
              background: currentView === item.view ? '#334155' : 'transparent',
              color: currentView === item.view ? '#60a5fa' : '#cbd5e1',
              cursor: 'pointer',
              fontSize: '0.875rem',
              textAlign: 'left',
              justifyContent: collapsed ? 'center' : 'flex-start',
              borderLeft: currentView === item.view ? '3px solid #60a5fa' : '3px solid transparent',
              transition: 'all 0.15s',
            }}
            title={collapsed ? item.label : undefined}
          >
            {item.icon}
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}

        {!collapsed && (
          <div style={{ padding: '1rem 1.25rem 0.5rem', fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            开发工具
          </div>
        )}
        {toolItems.map((item) => (
          <button
            key={item.view}
            onClick={() => onNavigate(item.view)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              width: '100%',
              padding: collapsed ? '0.75rem 0' : '0.6rem 1.25rem',
              border: 'none',
              background: currentView === item.view ? '#334155' : 'transparent',
              color: currentView === item.view ? '#60a5fa' : '#94a3b8',
              cursor: 'pointer',
              fontSize: '0.875rem',
              textAlign: 'left',
              justifyContent: collapsed ? 'center' : 'flex-start',
              borderLeft: currentView === item.view ? '3px solid #60a5fa' : '3px solid transparent',
              transition: 'all 0.15s',
            }}
            title={collapsed ? item.label : undefined}
          >
            {item.icon}
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div
          style={{
            padding: '0.75rem 1.25rem',
            borderTop: '1px solid #334155',
            fontSize: '0.7rem',
            color: '#64748b',
          }}
        >
          v1.0.0 · 本地运行
        </div>
      )}
    </aside>
  )
}

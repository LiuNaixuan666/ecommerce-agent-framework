import { useState } from 'react'
import Sidebar, { type NavView } from './components/Sidebar'
import Dashboard from './components/Dashboard'
import PlatformDetail from './components/PlatformDetail'
import PlatformAccess from './components/PlatformAccess'
import ProductManagement from './components/ProductManagement'
import ReplyStrategy from './components/ReplyStrategy'
import RunLogs from './components/RunLogs'
import ChatInterface from './components/ChatInterface'
import MockShopWorkbench from './components/MockShopWorkbench'
import CustomerServiceHub from './components/CustomerServiceHub'

function App() {
  const [navView, setNavView] = useState<NavView>('dashboard')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [platformCode, setPlatformCode] = useState<string>('')

  const handleNavigate = (view: NavView) => {
    setNavView(view)
  }

  const handleNavigateToPlatform = (code: string) => {
    setPlatformCode(code)
    setNavView('platform-detail')
  }

  const handleBackToDashboard = () => {
    setNavView('dashboard')
  }

  const renderContent = () => {
    switch (navView) {
      case 'dashboard':
        return <Dashboard onNavigateToPlatform={handleNavigateToPlatform} />
      case 'platform-detail':
        return <PlatformDetail platformCode={platformCode} onBack={handleBackToDashboard} />
      case 'products':
        return <ProductManagement />
      case 'platform-access':
        return <PlatformAccess />
      case 'reply-strategy':
        return <ReplyStrategy />
      case 'run-logs':
        return <RunLogs />
      case 'mock':
        return <MockShopWorkbench />
      case 'platform-workbench':
        return <CustomerServiceHub />
      case 'chat':
        return <ChatInterface />
      default:
        return <Dashboard onNavigateToPlatform={handleNavigateToPlatform} />
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        backgroundColor: '#f1f5f9',
      }}
    >
      <Sidebar
        currentView={navView}
        onNavigate={handleNavigate}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      <main style={{ flex: 1, overflow: 'auto', minHeight: '100vh' }}>
        {renderContent()}
      </main>
    </div>
  )
}

export default App

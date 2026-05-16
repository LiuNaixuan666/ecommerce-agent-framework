import React from 'react'
import ChatInterface from './components/ChatInterface'

function App() {
  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#f3f4f6'
    }}>
      <header style={{
        backgroundColor: 'white',
        boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)'
      }}>
        <div style={{
          maxWidth: '80rem',
          margin: '0 auto',
          padding: '0 1rem 0 1rem'
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '1rem 0'
          }}>
            <h1 style={{
              fontSize: '1.5rem',
              fontWeight: 'bold',
              color: '#111827'
            }}>电商客服助手</h1>
            <div style={{
              fontSize: '0.875rem',
              color: '#6b7280'
            }}>AI驱动的智能客服系统</div>
          </div>
        </div>
      </header>
      <main style={{
        maxWidth: '80rem',
        margin: '0 auto',
        padding: '0 1rem 0 1rem',
        paddingTop: '2rem'
      }}>
        <ChatInterface />
      </main>
    </div>
  )
}

export default App
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

// 새로고침(F5) 시 항상 대시보드(/)로 이동
const navEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined
if (navEntry?.type === 'reload' && window.location.pathname !== '/') {
  window.location.replace('/')
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)

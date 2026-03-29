import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

// 새로고침(F5) 시 항상 대시보드(/)로 이동
// React 마운트 전에 처리해야 하며, 리다이렉트 시에는 React를 마운트하지 않음
let shouldRedirect = false
try {
  const navEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined
  if (navEntry?.type === 'reload' && window.location.pathname !== '/') {
    shouldRedirect = true
  }
} catch {
  // performance API 미지원 환경: 정상 마운트
}

if (shouldRedirect) {
  window.location.replace('/')
} else {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>,
  )
}

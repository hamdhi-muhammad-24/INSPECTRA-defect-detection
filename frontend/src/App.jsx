import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Navbar from './components/Navbar.jsx'
import Dashboard from './pages/Dashboard.jsx'
import History from './pages/History.jsx'
import Analytics from './pages/Analytics.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: { background: 'var(--surface)', color: 'var(--text-primary)', border: '1px solid var(--border)' },
          success: { iconTheme: { primary: '#3fb950', secondary: '#0d1117' } },
          error:   { iconTheme: { primary: '#f85149', secondary: '#0d1117' } },
        }}
      />
      <Navbar />
      <main className="main-content">
        <Routes>
          <Route path="/"          element={<Dashboard />} />
          <Route path="/history"   element={<History />} />
          <Route path="/analytics" element={<Analytics />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}

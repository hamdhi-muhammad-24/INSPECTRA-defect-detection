import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { getHealth } from '../api/apiClient.js'

function useSystemStatus() {
  const [status, setStatus] = useState(null)
  useEffect(() => {
    getHealth().then(setStatus).catch(() => setStatus(null))
  }, [])
  if (!status) return 'unknown'
  if (status.qdrant_configured && status.groq_configured) return 'ok'
  if (status.qdrant_configured || status.groq_configured) return 'partial'
  return 'fail'
}

export default function Navbar() {
  const sys = useSystemStatus()
  const [menuOpen, setMenuOpen] = useState(false)

  const dotClass = sys === 'ok' ? 'dot-ok' : sys === 'partial' ? 'dot-partial' : sys === 'fail' ? 'dot-fail' : 'dot-unknown'
  const label    = sys === 'ok' ? 'All systems online' : sys === 'partial' ? 'Partial' : sys === 'fail' ? 'Offline' : ''

  const close = () => setMenuOpen(false)

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <NavLink to="/" className="navbar-brand" onClick={close}>
          <span className="navbar-brand-icon">⬡</span>
          INSPECTRA
        </NavLink>

        <div className="navbar-links">
          <NavLink to="/" end   className={({ isActive }) => isActive ? 'active' : ''}>Dashboard</NavLink>
          <NavLink to="/history"   className={({ isActive }) => isActive ? 'active' : ''}>History</NavLink>
          <NavLink to="/analytics" className={({ isActive }) => isActive ? 'active' : ''}>Analytics</NavLink>
        </div>

        {label && (
          <div className="navbar-status">
            <span className={`nav-status-dot ${dotClass}`} />
            <span className="nav-status-label">{label}</span>
          </div>
        )}

        <button
          className={`nav-hamburger${menuOpen ? ' open' : ''}`}
          onClick={() => setMenuOpen(o => !o)}
          aria-label="Toggle navigation"
        >
          <span /><span /><span />
        </button>
      </div>

      {menuOpen && (
        <div className="navbar-mobile-menu" onClick={close}>
          <NavLink to="/" end   className={({ isActive }) => isActive ? 'active' : ''}>Dashboard</NavLink>
          <NavLink to="/history"   className={({ isActive }) => isActive ? 'active' : ''}>History</NavLink>
          <NavLink to="/analytics" className={({ isActive }) => isActive ? 'active' : ''}>Analytics</NavLink>
          {label && (
            <div className="mobile-status-row">
              <span className={`nav-status-dot ${dotClass}`} />
              <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{label}</span>
            </div>
          )}
        </div>
      )}
    </nav>
  )
}

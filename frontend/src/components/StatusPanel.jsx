import { useEffect, useState } from 'react'
import { getHealth } from '../api/apiClient.js'

function Dot({ ok, loading }) {
  if (loading) return <span className="status-dot dot-loading" />
  return <span className={`status-dot ${ok ? 'dot-ok' : 'dot-fail'}`} />
}

export default function StatusPanel() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  function fetch() {
    setLoading(true)
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetch()
    const id = setInterval(fetch, 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="status-panel card--glass">
      <div className="status-panel-title">System Status</div>
      <div className="status-items">
        <div className="status-item">
          <Dot ok={true} loading={false} />
          <span className="status-item-label">Backend API</span>
          <span className="status-item-value ok">Online</span>
        </div>
        <div className="status-item">
          <Dot ok={health?.qdrant_configured} loading={loading} />
          <span className="status-item-label">Qdrant (RAG)</span>
          <span className={`status-item-value ${health?.qdrant_configured ? 'ok' : 'fail'}`}>
            {loading ? '…' : health?.qdrant_configured ? 'Connected' : 'Offline'}
          </span>
        </div>
        <div className="status-item">
          <Dot ok={health?.groq_configured} loading={loading} />
          <span className="status-item-label">Groq LLM</span>
          <span className={`status-item-value ${health?.groq_configured ? 'ok' : 'fail'}`}>
            {loading ? '…' : health?.groq_configured ? 'Ready' : 'Not configured'}
          </span>
        </div>
        <div className="status-item">
          <span className="status-dot dot-neutral" />
          <span className="status-item-label">Vision Models</span>
          <span className="status-item-value neutral">Train to activate</span>
        </div>
      </div>
    </div>
  )
}

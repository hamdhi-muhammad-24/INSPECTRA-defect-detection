import { useEffect, useState } from 'react'
import HistoryTable from '../components/HistoryTable.jsx'
import { getStats } from '../api/apiClient.js'

function StatCard({ label, value, className }) {
  return (
    <div className={`stat-card card--glass ${className || ''}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value ?? '—'}</div>
    </div>
  )
}

export default function History() {
  const [stats, setStats]     = useState(null)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    getStats().then(setStats).catch(() => {})
  }, [refresh])

  return (
    <div className="history-page">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
        <h1 className="section-title" style={{ marginBottom: 0 }}>Inspection History</h1>
        <button className="btn-secondary btn-sm" onClick={() => setRefresh(r => r + 1)}>↺ Refresh</button>
      </div>
      <p className="section-subtitle">Browse, filter, and manage all past inspection records.</p>

      {stats && (
        <div className="stats-row" style={{ marginBottom: '1.5rem' }}>
          <StatCard label="Total Inspections"  value={stats.total} />
          <StatCard label="Normal"             value={stats.normal_count}       className="stat-normal" />
          <StatCard label="Defective"          value={stats.defective_count}    className="stat-defect" />
          <StatCard label="Needs Review"       value={stats.human_review_count} className="stat-review" />
        </div>
      )}

      <div className="card card--glass">
        <HistoryTable key={refresh} />
      </div>
    </div>
  )
}

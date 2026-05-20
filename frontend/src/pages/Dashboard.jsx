import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import UploadPanel   from '../components/UploadPanel.jsx'
import ResultPanel   from '../components/ResultPanel.jsx'
import EvidencePanel from '../components/EvidencePanel.jsx'
import ChatPanel     from '../components/ChatPanel.jsx'
import StatusPanel   from '../components/StatusPanel.jsx'
import { getStats }  from '../api/apiClient.js'

function StatCard({ label, value, className }) {
  return (
    <div className={`stat-card card--glass ${className || ''}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value ?? '—'}</div>
    </div>
  )
}

export default function Dashboard() {
  const [result, setResult]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [stats, setStats]     = useState(null)

  useEffect(() => {
    getStats().then(setStats).catch(() => {})
  }, [result])

  function handleResult(data, err) {
    if (err) {
      toast.error(err)
      return
    }
    setResult(data)
    if (data.status === 'quality_rejected') {
      toast.error('Image quality check failed — please retake the photo.')
    } else if (data.status === 'model_not_trained') {
      toast('Model not trained for this category.', { icon: '⚠️' })
    } else if (data.status === 'normal') {
      toast.success(`Inspection complete — No defect detected.`)
    } else if (data.status === 'defective') {
      toast(`Defect detected · Severity: ${data.severity || 'unknown'}`, {
        icon: '🔴',
        style: { border: '1px solid var(--danger)' },
      })
    }
  }

  return (
    <div>
      <h1 className="section-title">Dashboard</h1>
      <p className="section-subtitle">Upload a product image to run AI-powered defect inspection.</p>

      <StatusPanel />

      {stats && (
        <div className="stats-row">
          <StatCard label="Total Inspections"  value={stats.total} />
          <StatCard label="Normal"             value={stats.normal_count}       className="stat-normal" />
          <StatCard label="Defective"          value={stats.defective_count}    className="stat-defect" />
          <StatCard label="Needs Review"       value={stats.human_review_count} className="stat-review" />
        </div>
      )}

      <div className="dashboard-layout">
        <UploadPanel onResult={handleResult} loading={loading} setLoading={setLoading} />

        <div className="dashboard-right">
          <ResultPanel result={result} heatmapPath={result?.heatmap_path} />
          {result?.evidence?.length > 0 && <EvidencePanel evidence={result.evidence} />}
          <ChatPanel result={result} />
        </div>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { getHistory } from '../api/apiClient.js'

const SEVERITY_COLORS = {
  Normal: '#3fb950',
  Minor: '#d29922',
  Major: '#f0883e',
  Critical: '#f85149',
  'Human Review Required': '#a371f7',
}

const CATEGORIES = ['bottle', 'cable', 'metal_nut', 'screw', 'tile', 'toothbrush', 'transistor', 'zipper']

function StatCard({ label, value, sub, color }) {
  return (
    <div className="stat-card card--glass">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={color ? { color } : {}}>{value ?? '—'}</div>
      {sub && <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>{sub}</div>}
    </div>
  )
}

function SkeletonCard() {
  return <div className="stat-card skeleton" style={{ height: '90px' }} />
}

export default function Analytics() {
  const [records, setRecords] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getHistory(0, 500)
      .then(setRecords)
      .catch(() => setRecords([]))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="analytics-page">
        <h1 className="section-title">Analytics</h1>
        <p className="section-subtitle">Loading inspection data…</p>
        <div className="stats-row">{[1,2,3,4].map(i => <SkeletonCard key={i} />)}</div>
      </div>
    )
  }

  const total = records.length
  const defective = records.filter(r => r.status === 'defective').length
  const defectRate = total > 0 ? ((defective / total) * 100).toFixed(1) : '0.0'
  const avgScore = total > 0
    ? (records.reduce((s, r) => s + (r.anomaly_score ?? 0), 0) / total).toFixed(3)
    : '—'
  const needsReview = records.filter(r => r.human_review_required).length

  // ── Line chart: inspections per day (last 30 days) ────────────────────────
  const today = new Date()
  const dayMap = {}
  for (let i = 29; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(d.getDate() - i)
    const key = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    dayMap[key] = { date: key, Normal: 0, Defective: 0 }
  }
  records.forEach(r => {
    const d = new Date(r.created_at)
    const key = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    if (dayMap[key]) {
      if (r.status === 'normal') dayMap[key].Normal++
      else if (r.status === 'defective') dayMap[key].Defective++
    }
  })
  const lineData = Object.values(dayMap).filter(d => d.Normal + d.Defective > 0 || true).slice(-14)

  // ── Pie chart: severity distribution ─────────────────────────────────────
  const sevMap = {}
  records.forEach(r => {
    if (!r.severity) return
    sevMap[r.severity] = (sevMap[r.severity] || 0) + 1
  })
  const pieData = Object.entries(sevMap).map(([name, value]) => ({ name, value }))

  // ── Bar chart: per-category normal vs defective ───────────────────────────
  const catMap = {}
  CATEGORIES.forEach(c => { catMap[c] = { category: c.replace('_', ' '), Normal: 0, Defective: 0 } })
  records.forEach(r => {
    if (catMap[r.product_category]) {
      if (r.status === 'normal') catMap[r.product_category].Normal++
      else if (r.status === 'defective') catMap[r.product_category].Defective++
    }
  })
  const barData = Object.values(catMap).filter(c => c.Normal + c.Defective > 0)

  const isEmpty = total === 0

  return (
    <div className="analytics-page">
      <h1 className="section-title">Analytics</h1>
      <p className="section-subtitle">Inspection trends and defect statistics across all categories.</p>

      <div className="stats-row" style={{ marginBottom: '2rem' }}>
        <StatCard label="Total Inspections" value={total} />
        <StatCard label="Defect Rate" value={`${defectRate}%`} sub={`${defective} defective`} color={defective > 0 ? 'var(--danger)' : 'var(--success)'} />
        <StatCard label="Avg Anomaly Score" value={avgScore} />
        <StatCard label="Needs Human Review" value={needsReview} color={needsReview > 0 ? 'var(--warning)' : undefined} />
      </div>

      {isEmpty ? (
        <div className="empty-state card">
          <p style={{ fontSize: '1rem' }}>No inspection data yet.</p>
          <p>Run your first inspection on the Dashboard to see charts here.</p>
        </div>
      ) : (
        <div className="analytics-charts">
          {/* Line chart */}
          <div className="chart-card card--glass">
            <h3 className="chart-title">Inspections Over Time (Last 14 Days)</h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={lineData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} allowDecimals={false} />
                <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }} />
                <Legend />
                <Line type="monotone" dataKey="Normal" stroke="#3fb950" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="Defective" stroke="#f85149" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Pie chart */}
          {pieData.length > 0 && (
            <div className="chart-card card--glass">
              <h3 className="chart-title">Severity Distribution</h3>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                    {pieData.map((entry) => (
                      <Cell key={entry.name} fill={SEVERITY_COLORS[entry.name] || '#8b949e'} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Bar chart */}
          {barData.length > 0 && (
            <div className="chart-card chart-card--wide card--glass">
              <h3 className="chart-title">Results by Category</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={barData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="category" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                  <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }} />
                  <Legend />
                  <Bar dataKey="Normal" fill="#3fb950" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Defective" fill="#f85149" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

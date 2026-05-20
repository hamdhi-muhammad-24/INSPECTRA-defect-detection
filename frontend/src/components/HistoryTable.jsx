import { useEffect, useState } from 'react'
import { getHistory, deleteInspection } from '../api/apiClient.js'

const SEVERITY_OPTIONS  = ['', 'Normal', 'Minor', 'Major', 'Critical', 'Human Review Required']
const CATEGORY_OPTIONS  = ['', 'bottle', 'cable', 'metal_nut', 'screw', 'tile', 'toothbrush', 'transistor', 'zipper']
const PAGE_SIZE = 20

function severityBadgeClass(sev) {
  if (!sev) return 'badge-neutral'
  const s = sev.toLowerCase()
  if (s === 'normal') return 'badge-success'
  if (s === 'minor' || s === 'major') return 'badge-warning'
  return 'badge-danger'
}

function statusBadgeClass(status) {
  if (status === 'normal')    return 'badge-success'
  if (status === 'defective') return 'badge-danger'
  if (status === 'quality_rejected') return 'badge-warning'
  return 'badge-neutral'
}

function fmt(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
}

function exportCsv(rows) {
  const headers = ['ID', 'Category', 'Status', 'Severity', 'Score', 'Human Review', 'Date']
  const lines = rows.map(r => [
    r.inspection_id, r.product_category, r.status, r.severity ?? '',
    r.anomaly_score?.toFixed(4) ?? '', r.human_review_required ? 'Yes' : 'No',
    fmt(r.created_at),
  ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
  const csv = [headers.join(','), ...lines].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `inspectra_history_${Date.now()}.csv`
  a.click(); URL.revokeObjectURL(url)
}

export default function HistoryTable() {
  const [rows, setRows]           = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [page, setPage]           = useState(0)
  const [hasMore, setHasMore]     = useState(true)
  const [catFilter, setCatFilter] = useState('')
  const [sevFilter, setSevFilter] = useState('')
  const [sortField, setSortField] = useState('created_at')
  const [sortDir, setSortDir]     = useState('desc')
  const [deleting, setDeleting]   = useState(null)
  const [expanded, setExpanded]   = useState(null)

  async function load(pageNum = 0) {
    setLoading(true); setError(null)
    try {
      const data = await getHistory(pageNum * PAGE_SIZE, PAGE_SIZE)
      setRows(data); setHasMore(data.length === PAGE_SIZE)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(page) }, [page])

  async function handleDelete(id) {
    if (!window.confirm(`Delete inspection ${id}?`)) return
    setDeleting(id)
    try {
      await deleteInspection(id)
      setRows(r => r.filter(row => row.inspection_id !== id))
      if (expanded === id) setExpanded(null)
    } catch (err) { alert(`Delete failed: ${err.message}`) }
    finally { setDeleting(null) }
  }

  function toggleSort(field) {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortField(field); setSortDir('asc') }
  }

  function si(field) { return sortField === field ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '' }

  let filtered = rows
    .filter(r => !catFilter || r.product_category === catFilter)
    .filter(r => !sevFilter || r.severity === sevFilter)
  filtered = [...filtered].sort((a, b) => {
    const av = a[sortField] ?? '', bv = b[sortField] ?? ''
    const cmp = av < bv ? -1 : av > bv ? 1 : 0
    return sortDir === 'asc' ? cmp : -cmp
  })

  async function handleExport() {
    try {
      const all = await getHistory(0, 1000)
      exportCsv(all)
    } catch { exportCsv(rows) }
  }

  return (
    <div>
      <div className="history-filters">
        <select value={catFilter} onChange={e => setCatFilter(e.target.value)}>
          <option value="">All Categories</option>
          {CATEGORY_OPTIONS.filter(Boolean).map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
        </select>
        <select value={sevFilter} onChange={e => setSevFilter(e.target.value)}>
          <option value="">All Severities</option>
          {SEVERITY_OPTIONS.filter(Boolean).map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button className="btn-secondary btn-sm" onClick={() => load(page)}>Refresh</button>
        <button className="btn-secondary btn-sm" onClick={handleExport} style={{ marginLeft: 'auto' }}>
          Export CSV
        </button>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
          <span className="spinner" /> Loading…
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state"><p>No inspection records found.</p></div>
      ) : (
        <div className="history-table-wrap">
          <table className="history-table">
            <thead>
              <tr>
                <th onClick={() => toggleSort('inspection_id')}>ID{si('inspection_id')}</th>
                <th onClick={() => toggleSort('product_category')}>Category{si('product_category')}</th>
                <th onClick={() => toggleSort('status')}>Status{si('status')}</th>
                <th onClick={() => toggleSort('severity')}>Severity{si('severity')}</th>
                <th onClick={() => toggleSort('anomaly_score')}>Score{si('anomaly_score')}</th>
                <th>Review</th>
                <th onClick={() => toggleSort('created_at')}>Date{si('created_at')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, idx) => (
                <>
                  <tr key={row.inspection_id} className={idx % 2 === 0 ? 'row-even' : ''}>
                    <td className="monospace">{row.inspection_id}</td>
                    <td>{row.product_category?.replace('_', ' ')}</td>
                    <td><span className={`badge ${statusBadgeClass(row.status)}`}>{row.status?.replace('_', ' ')}</span></td>
                    <td>
                      {row.severity
                        ? <span className={`badge ${severityBadgeClass(row.severity)}`}>{row.severity}</span>
                        : <span style={{ color: 'var(--text-secondary)' }}>—</span>}
                    </td>
                    <td>{row.anomaly_score != null ? row.anomaly_score.toFixed(4) : <span style={{ color: 'var(--text-secondary)' }}>—</span>}</td>
                    <td>{row.human_review_required ? <span className="badge badge-warning">Yes</span> : <span style={{ color: 'var(--text-secondary)' }}>No</span>}</td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{fmt(row.created_at)}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <button className="btn-secondary btn-sm"
                          onClick={() => setExpanded(expanded === row.inspection_id ? null : row.inspection_id)}>
                          {expanded === row.inspection_id ? '▲' : '▼'}
                        </button>
                        <button className="btn-danger btn-sm"
                          onClick={() => handleDelete(row.inspection_id)}
                          disabled={deleting === row.inspection_id}>
                          {deleting === row.inspection_id ? '…' : 'Delete'}
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expanded === row.inspection_id && (
                    <tr key={`${row.inspection_id}-detail`} className="row-expand">
                      <td colSpan={8}>
                        <div className="row-expand-body">
                          {row.explanation && (
                            <div className="expand-field">
                              <div className="expand-label">AI Explanation</div>
                              <div className="expand-value">{row.explanation}</div>
                            </div>
                          )}
                          {row.possible_root_cause && (
                            <div className="expand-field">
                              <div className="expand-label">Possible Root Cause</div>
                              <div className="expand-value">{row.possible_root_cause}</div>
                            </div>
                          )}
                          {row.recommended_action && (
                            <div className="expand-field">
                              <div className="expand-label">Recommended Action</div>
                              <div className="expand-value">{row.recommended_action}</div>
                            </div>
                          )}
                          {!row.explanation && !row.possible_root_cause && (
                            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No detail available for this record.</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="pagination">
        <button className="btn-secondary btn-sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0 || loading}>← Prev</button>
        <span>Page {page + 1}</span>
        <button className="btn-secondary btn-sm" onClick={() => setPage(p => p + 1)} disabled={!hasMore || loading}>Next →</button>
      </div>
    </div>
  )
}

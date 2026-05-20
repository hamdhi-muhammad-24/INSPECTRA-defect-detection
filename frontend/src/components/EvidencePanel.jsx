import { useState } from 'react'

function EvidenceItem({ chunk, index }) {
  const [open, setOpen] = useState(index === 0)
  const doc   = chunk.document_name || 'Unknown document'
  const page  = chunk.page_number  != null ? `Page ${chunk.page_number}` : ''
  const score = chunk.score        != null ? `${(chunk.score * 100).toFixed(1)}% match` : ''
  const text  = chunk.text || ''

  return (
    <div className="evidence-item">
      <div className="evidence-header" onClick={() => setOpen((o) => !o)}>
        <span className="evidence-doc" title={doc}>{doc}</span>
        <span className="evidence-meta">
          {[page, score].filter(Boolean).join(' · ')}
        </span>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginLeft: '0.4rem' }}>
          {open ? '▲' : '▼'}
        </span>
      </div>
      {open && (
        <div className="evidence-body">
          {text.length > 600 ? text.slice(0, 600) + '…' : text}
        </div>
      )}
    </div>
  )
}

export default function EvidencePanel({ evidence }) {
  const [collapsed, setCollapsed] = useState(false)

  if (!evidence || evidence.length === 0) return null

  return (
    <div className="card card--glass evidence-panel">
      <div className="panel-label" onClick={() => setCollapsed((c) => !c)}
        style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span>SOP Evidence</span>
        <span className="badge badge-info" style={{ fontSize: '0.7rem' }}>{evidence.length}</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          {collapsed ? '▼ Show' : '▲ Hide'}
        </span>
      </div>

      {!collapsed && (
        <div>
          {evidence.map((chunk, i) => (
            <EvidenceItem key={i} chunk={chunk} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}

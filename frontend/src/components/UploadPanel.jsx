import { useRef, useState } from 'react'
import { fullInspection } from '../api/apiClient.js'

const CATEGORIES = [
  { value: 'bottle',     label: 'Bottle' },
  { value: 'cable',      label: 'Cable' },
  { value: 'metal_nut',  label: 'Metal Nut' },
  { value: 'screw',      label: 'Screw' },
  { value: 'tile',       label: 'Tile' },
  { value: 'toothbrush', label: 'Toothbrush' },
  { value: 'transistor', label: 'Transistor' },
  { value: 'zipper',     label: 'Zipper' },
]

export default function UploadPanel({ onResult, loading, setLoading }) {
  const [category, setCategory] = useState('bottle')
  const [file, setFile]         = useState(null)
  const [preview, setPreview]   = useState(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError]       = useState(null)
  const inputRef = useRef()

  function handleFile(f) {
    if (!f) return
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setError(null)
  }

  function clearFile() {
    setFile(null)
    setPreview(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  async function handleAnalyze() {
    if (!file) { setError('Please select an image first.'); return }
    setError(null)
    setLoading(true)
    try {
      const result = await fullInspection(file, category)
      onResult(result)
    } catch (err) {
      setError(err.message)
      onResult(null, err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card card--glass upload-panel">
      <div className="panel-label">Product Inspection</div>

      <div className="category-select-wrap">
        <select value={category} onChange={e => setCategory(e.target.value)} disabled={loading}>
          {CATEGORIES.map(c => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </div>

      {preview ? (
        <>
          <img src={preview} alt="preview" className="image-preview" />
          <div className="upload-actions" style={{ marginBottom: '0.75rem' }}>
            <button className="btn-secondary btn-sm" onClick={clearFile} disabled={loading}>
              ✕ Remove
            </button>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {file.name}
            </span>
          </div>
        </>
      ) : (
        <div
          className={`drop-zone${dragging ? ' dragging' : ''}`}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
          onClick={() => inputRef.current?.click()}
        >
          <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/bmp,image/tiff"
            onChange={e => handleFile(e.target.files[0])} style={{ display: 'none' }} />
          <span className="drop-zone-icon">📷</span>
          <p>Drag & drop or click to select</p>
          <p className="hint">JPEG · PNG · BMP · TIFF — max 20 MB</p>
        </div>
      )}

      {error && <div className="banner banner-error">{error}</div>}

      <div className="upload-actions">
        <button className="btn-primary" onClick={handleAnalyze} disabled={loading || !file}>
          {loading ? <><span className="spinner" /> Analysing…</> : '⚡ Analyze'}
        </button>
      </div>
    </div>
  )
}

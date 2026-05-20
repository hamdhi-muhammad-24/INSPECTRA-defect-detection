import { useState } from 'react'
import { generateReport, downloadReportUrl } from '../api/apiClient.js'
import ScoreGauge from './ScoreGauge.jsx'

function severityBadgeClass(sev) {
  if (!sev) return 'badge-neutral'
  const s = sev.toLowerCase()
  if (s === 'normal')   return 'badge-success'
  if (s === 'minor')    return 'badge-warning'
  if (s === 'major')    return 'badge-warning'
  return 'badge-danger'
}

function qualityBadgeClass(q) {
  if (!q) return 'badge-neutral'
  if (q === 'PASS')              return 'badge-success'
  if (q === 'PASS_WITH_WARNING') return 'badge-warning'
  return 'badge-danger'
}

export default function ResultPanel({ result, heatmapPath }) {
  const [reportUrl, setReportUrl]     = useState(null)
  const [genLoading, setGenLoading]   = useState(false)
  const [genError, setGenError]       = useState(null)
  const [showHeatmap, setShowHeatmap] = useState(false)

  if (!result) {
    return (
      <div className="card card--glass result-panel fade-in-up">
        <div className="panel-label">Analysis Result</div>
        <div className="empty-state">
          <p>Upload an image and click Analyze to see results here.</p>
        </div>
      </div>
    )
  }

  const {
    inspection_id, product_category, status, anomaly_score, severity,
    human_review_required, image_quality, message, explanation,
    possible_root_cause, recommended_action, model_type, fallback_used,
    demo_mode,
  } = result

  const isQualityRejected = status === 'quality_rejected'
  const isNotTrained      = status === 'model_not_trained'
  const isNormal          = status === 'normal'

  const heatmapUrl = heatmapPath
    ? `http://localhost:8000/heatmaps/${heatmapPath.split(/[\\/]/).pop()}`
    : null

  async function handleGenerateReport() {
    setGenError(null)
    setGenLoading(true)
    try {
      const data = await generateReport(inspection_id)
      setReportUrl(downloadReportUrl(data.report_filename))
    } catch (err) {
      setGenError(err.message)
    } finally {
      setGenLoading(false)
    }
  }

  return (
    <div className="card card--glass result-panel fade-in-up">
      <div className="panel-label">Analysis Result</div>

      <div style={{ marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
        <span className="insp-id">{inspection_id}</span>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
          {product_category?.replace(/_/g, ' ')}
        </span>
        {demo_mode && <span className="badge badge-purple">Demo Mode</span>}
      </div>

      {image_quality && (
        <div style={{ marginBottom: '0.75rem' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginRight: '0.5rem' }}>Image Quality</span>
          <span className={`badge ${qualityBadgeClass(image_quality.quality_status)}`}>
            {image_quality.quality_status?.replace('_', ' ')}
          </span>
          {image_quality.warnings?.length > 0 && (
            <div className="banner banner-warning" style={{ marginTop: '0.5rem' }}>
              {image_quality.warnings.join(' · ')}
            </div>
          )}
        </div>
      )}

      {isQualityRejected && <div className="banner banner-error">{message}</div>}
      {isNotTrained && (
        <div className="banner banner-warning">
          Model for <strong>{product_category}</strong> is not trained yet. Run the training script first.
        </div>
      )}

      {!isQualityRejected && !isNotTrained && (
        <>
          <div className="result-header">
            <span className={`result-status-big ${isNormal ? 'normal' : 'defective'}`}>
              {isNormal ? '✓ Normal' : '✗ Defective'}
            </span>
            {severity && <span className={`badge ${severityBadgeClass(severity)}`}>{severity}</span>}
            {fallback_used && <span className="badge badge-warning">Fallback</span>}
            {demo_mode && <span className="badge badge-purple">Statistical Baseline</span>}
            {model_type && !demo_mode && <span className="badge badge-neutral">{model_type}</span>}
          </div>

          {anomaly_score != null && <ScoreGauge score={anomaly_score} />}

          {heatmapUrl && (
            <div style={{ margin: '0.75rem 0' }}>
              <button className="btn-secondary btn-sm" onClick={() => setShowHeatmap(v => !v)}>
                {showHeatmap ? 'Hide' : 'Show'} Anomaly Heatmap
              </button>
              {showHeatmap && (
                <img
                  src={heatmapUrl}
                  alt="Anomaly heatmap"
                  className="heatmap-img fade-in-up"
                />
              )}
            </div>
          )}

          {human_review_required && (
            <div className="human-review-flag">⚠ Human review required</div>
          )}

          {message && (
            <div className="result-field">
              <div className="result-field-label">Summary</div>
              <div className="result-field-value">{message}</div>
            </div>
          )}
          {explanation && (
            <div className="result-field">
              <div className="result-field-label">AI Explanation</div>
              <div className="result-field-value">{explanation}</div>
            </div>
          )}
          {possible_root_cause && (
            <div className="result-field">
              <div className="result-field-label">Possible Root Cause</div>
              <div className="result-field-value">{possible_root_cause}</div>
            </div>
          )}
          {recommended_action && (
            <div className="result-field">
              <div className="result-field-label">Recommended Action</div>
              <div className="result-field-value">{recommended_action}</div>
            </div>
          )}

          <div className="result-actions">
            {!reportUrl && (
              <button className="btn-secondary btn-sm" onClick={handleGenerateReport} disabled={genLoading}>
                {genLoading && <span className="spinner" />}
                {genLoading ? 'Generating…' : 'Generate PDF Report'}
              </button>
            )}
            {reportUrl && (
              <a href={reportUrl} download className="btn-primary btn-sm"
                style={{ padding: '0.3rem 0.8rem', fontSize: '0.8rem', borderRadius: 'var(--radius)' }}>
                Download PDF Report
              </a>
            )}
          </div>
          {genError && <div className="banner banner-error" style={{ marginTop: '0.5rem' }}>{genError}</div>}
        </>
      )}
    </div>
  )
}

import { useState } from 'react'
import { askChat } from '../api/apiClient.js'
import EvidencePanel from './EvidencePanel.jsx'

export default function ChatPanel({ result }) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading]   = useState(false)
  const [response, setResponse] = useState(null)
  const [error, setError]       = useState(null)

  const canAsk = result && result.status !== 'quality_rejected' && result.product_category

  async function handleAsk(e) {
    e.preventDefault()
    if (!question.trim() || !canAsk) return
    setError(null)
    setLoading(true)
    try {
      const prediction = {
        status:        result.status,
        defect_type:   'unknown_anomaly',
        anomaly_score: result.anomaly_score,
        severity:      result.severity,
      }
      const data = await askChat(question.trim(), result.product_category, prediction)
      setResponse(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card card--glass chat-panel">
      <div className="panel-label">Ask AI</div>

      {!canAsk && (
        <p style={{ fontSize: '0.875rem', marginBottom: '0.75rem' }}>
          Run an analysis first to enable follow-up questions.
        </p>
      )}

      <form className="chat-input-row" onSubmit={handleAsk}>
        <input
          type="text"
          placeholder="e.g. What caused this defect?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={loading || !canAsk}
        />
        <button className="btn-primary btn-sm" type="submit" disabled={loading || !canAsk || !question.trim()}>
          {loading ? <span className="spinner" /> : 'Ask'}
        </button>
      </form>

      {error && <div className="banner banner-error" style={{ marginTop: '0.75rem' }}>{error}</div>}

      {response && (
        <div className="chat-answer">
          {response.answer && (
            <div className="result-field">
              <div className="result-field-label">Answer</div>
              <div className="result-field-value">{response.answer}</div>
            </div>
          )}
          {response.possible_root_cause && (
            <div className="result-field">
              <div className="result-field-label">Possible Root Cause</div>
              <div className="result-field-value">{response.possible_root_cause}</div>
            </div>
          )}
          {response.recommended_action && (
            <div className="result-field">
              <div className="result-field-label">Recommended Action</div>
              <div className="result-field-value">{response.recommended_action}</div>
            </div>
          )}
          {response.human_review_required && (
            <div className="human-review-flag" style={{ marginTop: '0.75rem' }}>
              ⚠ Human review recommended
            </div>
          )}
          {response.warning && (
            <div className="banner banner-warning" style={{ marginTop: '0.75rem' }}>{response.warning}</div>
          )}
          <EvidencePanel evidence={response.evidence} />
        </div>
      )}
    </div>
  )
}

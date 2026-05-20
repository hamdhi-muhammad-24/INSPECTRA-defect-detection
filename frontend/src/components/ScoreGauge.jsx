import { useEffect, useState } from 'react'

const RADIUS = 54
const CIRCUMFERENCE = Math.PI * RADIUS

function scoreColor(score) {
  if (score < 0.3) return '#3fb950'
  if (score < 0.6) return '#d29922'
  if (score < 0.75) return '#f0883e'
  return '#f85149'
}

function scoreLabel(score) {
  if (score < 0.3) return 'Normal'
  if (score < 0.5) return 'Minor'
  if (score < 0.7) return 'Major'
  if (score < 0.85) return 'Critical'
  return 'Review'
}

export default function ScoreGauge({ score }) {
  const [animated, setAnimated] = useState(0)

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(score ?? 0), 80)
    return () => clearTimeout(timer)
  }, [score])

  const pct = Math.max(0, Math.min(1, animated))
  const dash = pct * CIRCUMFERENCE
  const gap = CIRCUMFERENCE - dash
  const color = scoreColor(score ?? 0)

  return (
    <div className="score-gauge-wrap">
      <svg viewBox="0 0 120 70" className="score-gauge-svg">
        {/* Background arc */}
        <path
          d="M 10 65 A 54 54 0 0 1 110 65"
          fill="none"
          stroke="var(--surface-alt)"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Foreground arc */}
        <path
          d="M 10 65 A 54 54 0 0 1 110 65"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${gap}`}
          style={{ transition: 'stroke-dasharray 0.7s ease, stroke 0.4s ease' }}
        />
        {/* Score text */}
        <text x="60" y="58" textAnchor="middle" fontSize="18" fontWeight="700" fill={color}>
          {score != null ? `${Math.round(score * 100)}%` : '—'}
        </text>
        <text x="60" y="70" textAnchor="middle" fontSize="7" fill="var(--text-secondary)">
          ANOMALY SCORE
        </text>
      </svg>
      {score != null && (
        <div className="score-gauge-label" style={{ color }}>
          {scoreLabel(score)}
        </div>
      )}
    </div>
  )
}

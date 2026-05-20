import axios from 'axios'

const api = axios.create({ timeout: 120_000 })

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg).join(', ')
      : detail || err.message || 'Unknown error'
    return Promise.reject(new Error(message))
  },
)

// ── Predict ──────────────────────────────────────────────────────────────────

export function fullInspection(imageFile, category, userQuestion = '') {
  const fd = new FormData()
  fd.append('image', imageFile)
  fd.append('product_category', category)
  if (userQuestion) fd.append('user_question', userQuestion)
  return api.post('/api/predict/full-inspection', fd).then((r) => r.data)
}

export function analyzeImage(imageFile, category) {
  const fd = new FormData()
  fd.append('image', imageFile)
  fd.append('product_category', category)
  return api.post('/api/predict/analyze', fd).then((r) => r.data)
}

export function checkImageQuality(imageFile) {
  const fd = new FormData()
  fd.append('image', imageFile)
  return api.post('/api/predict/image-quality', fd).then((r) => r.data)
}

// ── Chat ─────────────────────────────────────────────────────────────────────

export function askChat(question, productCategory, prediction) {
  return api
    .post('/api/chat/ask', { question, product_category: productCategory, prediction })
    .then((r) => r.data)
}

// ── Reports ──────────────────────────────────────────────────────────────────

export function generateReport(inspectionId) {
  return api.post(`/api/reports/generate/${inspectionId}`).then((r) => r.data)
}

export function downloadReportUrl(filename) {
  return `/api/reports/download/${filename}`
}

// ── History ──────────────────────────────────────────────────────────────────

export function getHistory(skip = 0, limit = 50) {
  return api.get('/api/history', { params: { skip, limit } }).then((r) => r.data)
}

export function getInspection(inspectionId) {
  return api.get(`/api/history/${inspectionId}`).then((r) => r.data)
}

export function deleteInspection(inspectionId) {
  return api.delete(`/api/history/${inspectionId}`).then((r) => r.data)
}

export function getStats() {
  return api.get('/api/history/stats/summary').then((r) => r.data)
}

// ── Health ───────────────────────────────────────────────────────────────────

export function getHealth() {
  return api.get('/api/health').then((r) => r.data)
}

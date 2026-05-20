# INSPECTRA — AI Defect Detection & Root-Cause Assistant

INSPECTRA is a full-stack AI system for industrial quality inspection. Upload a product image, select a category, and the system determines whether the product is normal or defective. For defects it returns an anomaly score, severity level, AI-generated root-cause explanation, recommended action, SOP evidence retrieved from a vector store, and a downloadable PDF inspection report.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite |
| Backend | FastAPI (Python 3.10+) |
| Anomaly detection | Anomalib 1.x / PatchCore |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Vector database | Qdrant (Docker) |
| LLM | Groq API (llama-3.1-8b-instant) |
| Relational DB | SQLite via SQLAlchemy 2 |
| PDF reports | ReportLab |

## Supported product categories

`bottle` · `cable` · `metal_nut` · `screw` · `tile` · `toothbrush` · `transistor` · `zipper`

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | |
| Node.js 18+ | |
| Docker Desktop | Must be running before Step 5 |
| Groq API key | Free at https://console.groq.com |
| MVTec AD dataset | https://www.mvtec.com/company/research/datasets/mvtec-ad — place at `data/mvtec_ad/` |

---

## Setup — step by step

All commands below are run from the **project root** (`INSPECTRA_Defect_Detection/`) unless a `cd` is shown.

---

### Step 1 — Create virtual environment

```bash
python -m venv .venv
```

---

### Step 2 — Activate environment

**Windows:**

```bash
.\.venv\Scripts\activate
```

**macOS / Linux:**

```bash
source .venv/bin/activate
```

You should see `(.venv)` in your prompt. Keep this terminal open — all remaining Python commands use this environment.

---

### Step 3 — Install backend requirements

```bash
cd backend
pip install -r requirements.txt
```

> **GPU note:** `requirements.txt` installs the CPU build of PyTorch by default.
> For CUDA 12.1 GPU support, install PyTorch separately first:
> ```bash
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
> ```
> Then re-run `pip install -r requirements.txt`.

Go back to project root when done:

```bash
cd ..
```

---

### Step 4 — Create backend/.env

```bash
copy backend\.env.example backend\.env
```

Open `backend/.env` and set your real Groq API key:

```
GROQ_API_KEY=gsk_...
```

All other defaults work for local development. Do **not** commit this file.

---

### Step 5 — Start Qdrant (vector store)

```bash
docker compose up -d
```

Verify Qdrant is running:

```
http://localhost:6333/dashboard
```

---

### Step 6 — Test Qdrant connection

```bash
python scripts/test_qdrant_connection.py
```

Expected output:

```
Connecting to Qdrant at http://localhost:6333 ...
  Connected successfully.
  Collections found: 0
  Collection 'inspectra_rag_documents' does not exist yet.
  Run: python scripts/ingest_rag_documents.py
```

---

### Step 7 — Ingest RAG documents

Place your SOP/QA PDF files in `data/rag_documents/`, then run:

```bash
python scripts/ingest_rag_documents.py
```

Expected output:

```
Found N PDF(s) in data/rag_documents
Loading embedding model: sentence-transformers/all-MiniLM-L6-v2
  (first run downloads ~90 MB — subsequent runs use cache)
...
Ingestion complete.
  Collection : inspectra_rag_documents
  Total vectors: XXXX
```

Re-run at any time to refresh the collection — the script is idempotent.

---

### Step 8 — Train a model (one category)

```bash
python scripts/train_patchcore.py --category bottle --image-size 256 --batch-size 1
```

Trained artifacts are saved to `models/trained/bottle/`.

**Train all 8 categories** (recommended order for limited GPU memory):

```bash
python scripts/train_patchcore.py --category bottle       --image-size 256 --batch-size 1
python scripts/train_patchcore.py --category metal_nut    --image-size 256 --batch-size 1
python scripts/train_patchcore.py --category transistor   --image-size 256 --batch-size 1
python scripts/train_patchcore.py --category tile         --image-size 256 --batch-size 1
python scripts/train_patchcore.py --category cable        --image-size 256 --batch-size 1
python scripts/train_patchcore.py --category screw        --image-size 256 --batch-size 1
python scripts/train_patchcore.py --category zipper       --image-size 256 --batch-size 1
python scripts/train_patchcore.py --category toothbrush   --image-size 256 --batch-size 1
```

To evaluate a trained model:

```bash
python scripts/evaluate_model.py --category bottle
# results → evaluation/vision_tests/bottle_evaluation.json
```

---

### Step 9 — Start backend

Open a new terminal (with `.venv` activated), then:

```bash
cd backend
uvicorn app.main:app --reload
```

Backend URL: `http://localhost:8000`  
Swagger docs: `http://localhost:8000/docs`  
Health check: `http://localhost:8000/api/health`

Expected health response:

```json
{
  "status": "ok",
  "service": "INSPECTRA backend",
  "qdrant_configured": true,
  "groq_configured": true
}
```

---

### Step 10 — Start frontend

Open another new terminal (no `.venv` needed), then:

```bash
cd frontend
npm install
npm run dev
```

---

### Step 11 — Open the app

```
http://localhost:5173
```

- **Dashboard** — upload an image, select a category, click Analyze.
- **History** — browse all past inspections, view stats, delete records.

---

## Dataset directory structure

Place the MVTec AD dataset at `data/mvtec_ad/`. The dataset uses a double-folder structure (standard MVTec AD layout):

```
data/
└── mvtec_ad/
    ├── bottle/
    │   └── bottle/
    │       ├── train/
    │       │   └── good/        ← normal images used for training
    │       └── test/
    │           ├── good/
    │           ├── broken_large/
    │           └── ...
    ├── cable/
    │   └── cable/
    │       └── ...
    └── ...
```

`data/mvtec_ad/` is git-ignored. `data/rag_documents/` is tracked.

---

## Environment variables

All variables are read from `backend/.env` (never committed).

| Variable | Description | Default |
|---|---|---|
| `GROQ_API_KEY` | Groq LLM API key | *(required)* |
| `GROQ_MODEL` | Groq model ID | `llama-3.1-8b-instant` |
| `QDRANT_URL` | Qdrant endpoint | `http://localhost:6333` |
| `QDRANT_API_KEY` | Qdrant API key (cloud only) | *(empty)* |
| `QDRANT_COLLECTION_NAME` | Vector collection name | `inspectra_rag_documents` |
| `DATASET_PATH` | MVTec AD root, relative to `backend/` | `../data/mvtec_ad` |
| `RAG_DOCS_PATH` | PDF documents folder | `../data/rag_documents` |
| `MODEL_DIR` | Trained checkpoint folder | `../models/trained` |
| `REPORTS_DIR` | Generated PDF output folder | `../reports/generated_reports` |
| `DATABASE_URL` | SQLite connection string | `sqlite:///./inspectra.db` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:5173` |

---

## API reference

All routes are prefixed `/api`. Full interactive docs at `http://localhost:8000/docs`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Service health + Qdrant/Groq status |
| `POST` | `/api/predict/image-quality` | Standalone image quality check |
| `POST` | `/api/predict/analyze` | Anomaly detection only (no LLM) |
| `POST` | `/api/predict/full-inspection` | Full pipeline: quality → anomaly → RAG → Groq |
| `POST` | `/api/rag/search` | Search SOP evidence by query |
| `POST` | `/api/rag/ingest` | Trigger RAG document ingestion (background) |
| `POST` | `/api/chat/ask` | Ask a follow-up question about an inspection |
| `POST` | `/api/reports/generate/{id}` | Generate PDF report for an inspection |
| `GET` | `/api/reports/download/{filename}` | Download a generated PDF |
| `GET` | `/api/reports/list` | List all generated reports |
| `GET` | `/api/history` | Paginated inspection history |
| `GET` | `/api/history/stats/summary` | Aggregate statistics |
| `GET` | `/api/history/{id}` | Full record for one inspection |
| `DELETE` | `/api/history/{id}` | Delete an inspection record |

---

## Project structure

```
INSPECTRA_Defect_Detection/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── health.py
│   │   │   ├── predict.py        # image-quality · analyze · full-inspection
│   │   │   ├── rag.py
│   │   │   ├── chat.py
│   │   │   ├── reports.py
│   │   │   └── history.py
│   │   ├── core/
│   │   │   ├── config.py         # pydantic-settings
│   │   │   └── database.py       # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   └── inspection_record.py
│   │   ├── schemas/
│   │   │   ├── prediction_schema.py
│   │   │   ├── chat_schema.py
│   │   │   └── history_schema.py
│   │   ├── services/
│   │   │   ├── anomaly_service.py    # PatchCore inference + model cache
│   │   │   ├── image_quality_service.py
│   │   │   ├── severity_service.py
│   │   │   ├── rag_service.py        # Qdrant search + ingestion
│   │   │   ├── groq_service.py       # Groq LLM explanation
│   │   │   ├── history_service.py    # SQLite CRUD + stats
│   │   │   └── report_service.py     # ReportLab PDF generation
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── apiClient.js
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   ├── UploadPanel.jsx
│   │   │   ├── ResultPanel.jsx
│   │   │   ├── EvidencePanel.jsx
│   │   │   ├── ChatPanel.jsx
│   │   │   └── HistoryTable.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   └── History.jsx
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   └── vite.config.js            # port 5173, proxy /api → localhost:8000
├── scripts/
│   ├── train_patchcore.py
│   ├── evaluate_model.py
│   ├── ingest_rag_documents.py
│   └── test_qdrant_connection.py
├── data/
│   ├── mvtec_ad/                 # git-ignored — place MVTec AD here
│   └── rag_documents/            # tracked   — SOP/QA PDF documents
├── models/
│   └── trained/                  # git-ignored — PatchCore checkpoints
├── reports/
│   └── generated_reports/        # git-ignored — PDF reports
├── vector_store/
│   └── qdrant_storage/           # git-ignored — Qdrant Docker volume
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## Troubleshooting

### Docker not running

**Symptom:** Step 5 or Step 6 fails immediately.

```
error during connect: ... Is the docker daemon running?
```

**Fix:** Start Docker Desktop, wait for it to fully start, then re-run:

```bash
docker compose up -d
```

---

### Qdrant connection failed

**Symptom:** `python scripts/test_qdrant_connection.py` prints `ERROR: Could not connect to Qdrant`.

**Checklist:**
1. Docker is running: `docker ps` should show `qdrant/qdrant`.
2. Port 6333 is not blocked by another process.
3. If you changed `QDRANT_URL` in `.env`, make sure it matches `docker-compose.yml`.

**Fix:**

```bash
docker compose down
docker compose up -d
python scripts/test_qdrant_connection.py
```

---

### GROQ_API_KEY not configured

**Symptom:** `/api/health` returns `"groq_configured": false`. Full-inspection results have `explanation: null`. Chat endpoint returns HTTP 503.

**Fix:** Open `backend/.env` and set a real key:

```
GROQ_API_KEY=gsk_...
```

Get a free key at https://console.groq.com. Restart the backend after saving.

---

### Model not trained for selected category

**Symptom:** Response status is `model_not_trained`. Frontend shows banner "Model for \<category\> is not trained yet."

**Fix:** Train the model (run from project root with `.venv` active):

```bash
python scripts/train_patchcore.py --category <category> --image-size 256 --batch-size 1
```

The checkpoint `models/trained/<category>/model.ckpt` must exist before that category can be analyzed.

---

### CUDA out of memory

**Symptom:** Training crashes with `CUDA out of memory` or `RuntimeError: CUDA error`.

**Notes:** The training script automatically retries on CPU when a CUDA OOM is detected. If you want to skip GPU entirely from the start:

```bash
python scripts/train_patchcore.py --category bottle --device cpu
```

CPU training takes longer (15–60 min per category) but uses no GPU memory.

---

### Dataset path not found

**Symptom:** Training exits with `ERROR: Dataset not found at ...`.

**Checklist:**
1. Dataset is placed at `data/mvtec_ad/` relative to the project root.
2. The folder uses the double-folder structure: `data/mvtec_ad/bottle/bottle/train/good/`.
3. `DATASET_PATH` in `backend/.env` is `../data/mvtec_ad` (correct default).

To verify:

```bash
# Windows
dir data\mvtec_ad\bottle\bottle\train\good
# macOS / Linux
ls data/mvtec_ad/bottle/bottle/train/good
```

---

### CORS error in browser

**Symptom:** Browser console shows `Access-Control-Allow-Origin` errors. API calls from the frontend fail.

**Fix:** Ensure `CORS_ORIGINS` in `backend/.env` includes the frontend origin:

```
CORS_ORIGINS=http://localhost:5173
```

For multiple origins:

```
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

Restart the backend after changing this value. In development, the Vite proxy (`/api → http://localhost:8000`) handles all API calls so CORS should not be an issue unless you bypass the proxy.

---

## Git-ignored paths (final check)

The following paths are excluded from version control:

| Path | Reason |
|---|---|
| `backend/.env` | Contains real API keys — never commit |
| `data/mvtec_ad/` | Dataset is several GB — never commit |
| `models/trained/` | Trained checkpoints — generated locally |
| `vector_store/qdrant_storage/` | Qdrant runtime data |
| `reports/generated_reports/` | Generated PDF reports |
| `backend/inspectra.db` | SQLite runtime database |

`data/rag_documents/` is **tracked** — these PDF documents seed the RAG pipeline and must be committed.

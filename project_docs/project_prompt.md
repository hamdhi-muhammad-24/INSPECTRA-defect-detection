You are building a complete full-stack AI project called INSPECTRA_DEFECT_DETECTION.

Project idea:
INSPECTRA is an AI Defect Detection and Root-Cause Assistant for industrial quality inspection. The user uploads a product image from the MVTec AD dataset, selects the product category, and the system checks whether the product is normal or defective. If defective, the system returns anomaly status, anomaly score, severity level, possible root cause, recommended operator action, retrieved SOP/QA evidence, and a downloadable PDF inspection report.

The system must combine:
1. React frontend
2. FastAPI backend
3. MVTec AD dataset
4. Anomalib/PatchCore anomaly detection
5. Image quality checking
6. Qdrant vector database for RAG
7. Groq API for LLM explanation
8. SQLite for inspection history
9. PDF report generation
10. Chat/question box using RAG

Dataset:
The MVTec AD dataset is already downloaded and extracted inside:
data/mvtec_ad/

The project must support these 8 categories:
- bottle
- cable
- screw
- transistor
- tile
- toothbrush
- zipper
- metal_nut

Each category follows the official MVTec AD structure:
category/
├── train/good/
├── test/good/
├── test/<defect_type>/
└── ground_truth/<defect_type>/

RAG documents:
The RAG PDF documents are already inside:
data/rag_documents/

Documents:
- QA_Inspection_Manual_MVTec_AD.pdf
- Defect_Severity_Guide.pdf
- Operator_Action_SOP.pdf
- Root_Cause_Troubleshooting_Guide.pdf
- Inspection_Report_Template.pdf
- Image_Quality_Check_SOP.pdf
- Human_Review_and_Escalation_Policy.pdf

LLM:
Use Groq API for LLM responses. The real API key must be read only from backend/.env.
Do not hardcode API keys.

Vector database:
Use Qdrant locally through Docker. Store document chunks and embeddings in Qdrant.

Backend:
Use FastAPI. The backend must expose endpoints for:
- health check
- image prediction
- RAG document ingestion
- chat/question answering
- report generation
- inspection history

Frontend:
Use React with a modern attractive UI. The website should look like a professional SaaS dashboard. It must include:
- image upload
- category selection
- image preview
- image quality result
- anomaly detection result
- anomaly score
- severity level
- possible root cause
- recommended operator action
- RAG evidence panel
- PDF report download
- inspection history
- chat/question box

Model:
Use Anomalib/PatchCore-based anomaly detection suitable for MVTec AD.
Because the user has limited GPU memory, train category-by-category using small image sizes and batch size 1 or small batch size. Add CPU fallback.
The system must support all 8 categories, but training should be done one category at a time.

Important rules:
- Do not move, delete, or duplicate the dataset.
- Do not push dataset files to GitHub.
- Do not commit .env files or API keys.
- Keep code modular and clean.
- Add clear README instructions.
- Make the project runnable locally.
- If Anomalib installation or training is heavy, create a clean model service interface and add a fallback baseline, but keep PatchCore/Anomalib as the main intended model.
- Every phase must be testable before moving to the next phase.
# EquiHire analysis API

The API accepts a PDF or DOCX as base64 JSON, extracts text in memory, then returns a resume profile, skills mentioned, supporting excerpts, and evidence coverage for the selected role criteria. It does not write resumes or results to disk or to a database.

## Run locally

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

The health endpoint is `http://localhost:8000/health`. The analysis endpoint is `POST http://localhost:8000/analyze`.

The current matcher uses a curated skill vocabulary and phrase matching as a transparent baseline. It does not estimate hiring outcomes or validate skill proficiency. Scanned PDFs are not supported until OCR is added.

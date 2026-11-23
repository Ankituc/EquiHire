# EquiHire

A session-only resume review prototype. The React UI sends a selected PDF or DOCX to a Python API, which extracts text in memory and returns skill mentions, source excerpts, candidate details, and requirement matching. A TF-IDF vectorizer with cosine-distance KNN ranks the closest resume passage for each requirement. The UI visualizes direct matches, related text, and missing evidence, alongside an explainable decision-tree-style triage.

## Start the API

```bash
cd /Users/ankit/Desktop/NOVEMBER
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

The API documentation is at <http://localhost:8000/docs> while the server is running.

## Start the UI

In a second terminal:

```bash
cd /Users/ankit/Desktop/NOVEMBER
npm run dev
```

Vite serves the app at <http://localhost:5173>. The UI calls `http://localhost:8000/analyze`; set `VITE_API_URL` if the API runs elsewhere.

## Current analysis limits

The analysis uses PDF/DOCX text extraction and a curated skill vocabulary with phrase matching. KNN similarity finds related passages that may not use the exact same wording. The evidence triage is an explainable rule baseline, not a trained proficiency model. Accuracy, precision, recall, and F1 are not reported because a labeled evaluation dataset has not been supplied. Evidence coverage does not measure proficiency or predict hiring outcomes. Scanned PDFs need OCR, and an unfamiliar role needs explicit job requirements for coverage calculation. Resume content is kept in request memory and browser session state only; clearing the review removes the selected file and displayed results.

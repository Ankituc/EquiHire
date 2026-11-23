# EquiHire analysis API

The API accepts a PDF or DOCX as base64 JSON, extracts text in memory, then returns a resume profile, skill mentions and extraction quality metrics, and evidence coverage for the selected role criteria. It does not write resumes or results to disk or to a database.

## Run locally

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

The health endpoint is `http://localhost:8000/health`. To allow a deployed frontend, set `EQUIHIRE_ALLOWED_ORIGINS` to comma-separated origins before starting the API. The analysis endpoint is `POST http://localhost:8000/analyze`.

The matcher uses a curated skill vocabulary and phrase matching as a transparent baseline. Resume snippets are not included in API responses; direct mentions are counted in memory. It does not estimate hiring outcomes or validate skill proficiency. The API reports extraction character counts and warns when very little text is selectable. When Tesseract is installed, image-based PDF pages receive best-effort OCR (up to eight pages). Other files still use selectable text extraction.

The separate offline ML evaluation workflow is documented in the project root [README](../README.md). It uses the public CareerCorpus research dataset; the upload API never writes user resumes into that dataset.

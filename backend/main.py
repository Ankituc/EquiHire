"""EquiHire's session-only resume analysis API.

Uploaded content is accepted as JSON base64 and processed from memory. This
service deliberately has no database, file writes, logging of resume text, or
persistent upload directory.
"""

from __future__ import annotations

import base64
import binascii
import io
import re
import unicodedata
import zipfile
from collections import Counter
from typing import Any

import fitz
from docx import Document
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

MAX_RESUME_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARS = 300_000
MAX_PDF_PAGES = 150

app = FastAPI(title="EquiHire Analysis API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class AnalyzeRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    target_role: str = Field(min_length=1, max_length=160)
    job_requirements: str = Field(default="", max_length=20_000)


# Curated baseline vocabulary for the prototype. It is intentionally explicit
# and explainable; this is not a trained competency or hiring model.
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "SQL": ("sql", "structured query language"),
    "JavaScript": ("javascript", "js"),
    "TypeScript": ("typescript",),
    "React": ("react", "react.js", "reactjs"),
    "HTML": ("html", "html5"),
    "CSS": ("css", "css3"),
    "Tableau": ("tableau",),
    "Power BI": ("power bi", "powerbi"),
    "Excel": ("excel", "microsoft excel"),
    "Statistics": ("statistics", "statistical analysis"),
    "Machine learning": ("machine learning", "ml"),
    "scikit-learn": ("scikit-learn", "scikit learn", "sklearn"),
    "TensorFlow": ("tensorflow",),
    "PyTorch": ("pytorch",),
    "NLP": ("natural language processing", "nlp"),
    "A/B testing": ("a/b testing", "ab testing", "a/b test", "ab test"),
    "Experiment design": ("experiment design", "experimental design"),
    "Data visualization": ("data visualization", "data visualisation"),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure", "microsoft azure"),
    "Docker": ("docker",),
    "Git": ("git", "github", "gitlab"),
    "Java": ("java",),
    "C++": ("c++", "cpp"),
    "Node.js": ("node.js", "nodejs", "node js"),
    "REST APIs": ("rest api", "rest apis", "restful api", "restful apis"),
    "FastAPI": ("fastapi",),
    "Figma": ("figma",),
    "User research": ("user research",),
    "Usability testing": ("usability testing", "usability test"),
    "Design systems": ("design system", "design systems"),
}

ROLE_CRITERIA: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("product analyst", "product data analyst", "product analytics"), ("SQL", "Python", "A/B testing", "Statistics", "Tableau")),
    (("data analyst", "business analyst", "analytics analyst"), ("SQL", "Excel", "Statistics", "Data visualization")),
    (("data scientist", "data science"), ("Python", "SQL", "Statistics", "Machine learning", "scikit-learn")),
    (("machine learning engineer", "ml engineer", "ml engineer"), ("Python", "Machine learning", "scikit-learn", "TensorFlow", "PyTorch")),
    (("frontend engineer", "front end engineer", "frontend developer", "front end developer"), ("JavaScript", "React", "HTML", "CSS", "TypeScript")),
    (("backend engineer", "back end engineer", "backend developer", "back end developer"), ("Python", "SQL", "REST APIs", "Docker", "Git")),
    (("software engineer", "software developer"), ("Python", "JavaScript", "SQL", "Git")),
    (("ux designer", "product designer", "user experience designer"), ("Figma", "User research", "Usability testing", "Design systems")),
)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[\t\r ]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def extract_pdf(data: bytes) -> list[dict[str, str]]:
    try:
        with fitz.open(stream=data, filetype="pdf") as pdf:
            if pdf.page_count > MAX_PDF_PAGES:
                raise HTTPException(status_code=413, detail="The PDF has too many pages (maximum 150).")
            blocks = []
            for index, page in enumerate(pdf):
                text = normalize_text(page.get_text("text"))
                if text:
                    blocks.append({"text": text, "source": f"PDF · p. {index + 1}"})
            return blocks
    except HTTPException:
        raise
    except Exception as exc:  # PyMuPDF raises multiple format-specific errors.
        raise HTTPException(status_code=422, detail="This PDF could not be read. Try exporting it again as a text-based PDF.") from exc


def extract_docx(data: bytes) -> list[dict[str, str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            expanded_size = sum(item.file_size for item in archive.infolist())
            if expanded_size > 40 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="This DOCX expands to too much content to process safely.")
        document = Document(io.BytesIO(data))
        blocks: list[dict[str, str]] = []
        for index, paragraph in enumerate(document.paragraphs, start=1):
            text = normalize_text(paragraph.text)
            if text:
                blocks.append({"text": text, "source": f"DOCX · paragraph {index}"})
        for table_index, table in enumerate(document.tables, start=1):
            for row_index, row in enumerate(table.rows, start=1):
                text = normalize_text(" | ".join(cell.text for cell in row.cells))
                if text:
                    blocks.append({"text": text, "source": f"DOCX · table {table_index}, row {row_index}"})
        return blocks
    except HTTPException:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="This DOCX file could not be read. Try saving it again from Word or Google Docs.") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail="This DOCX file could not be read. Try saving it again from Word or Google Docs.") from exc


def decode_resume(filename: str, encoded: str) -> tuple[list[dict[str, str]], str]:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in {"pdf", "docx"}:
        raise HTTPException(status_code=415, detail="Upload a PDF or DOCX resume.")
    max_encoded_chars = ((MAX_RESUME_BYTES + 2) // 3) * 4
    if len(encoded) > max_encoded_chars:
        raise HTTPException(status_code=413, detail="The resume must be 10 MB or smaller.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="The uploaded file could not be decoded.") from exc
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="The resume must be 10 MB or smaller.")
    if extension == "pdf":
        if not data.startswith(b"%PDF-"):
            raise HTTPException(status_code=415, detail="The file content does not look like a PDF.")
        blocks = extract_pdf(data)
    else:
        if not data.startswith(b"PK"):
            raise HTTPException(status_code=415, detail="The file content does not look like a DOCX document.")
        blocks = extract_docx(data)
    text_length = sum(len(block["text"]) for block in blocks)
    if text_length > MAX_EXTRACTED_CHARS:
        raise HTTPException(status_code=413, detail="The extracted text is too long to analyze safely.")
    if not any(block["text"] for block in blocks):
        raise HTTPException(status_code=422, detail="No selectable text was found. Scanned PDFs need OCR, which is not included yet.")
    return blocks, extension


def contains_term(text: str, term: str) -> bool:
    pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def find_occurrences(blocks: list[dict[str, str]], aliases: tuple[str, ...]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for block in blocks:
        for alias in aliases:
            match = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", block["text"], flags=re.IGNORECASE)
            if match:
                start = max(0, match.start() - 80)
                end = min(len(block["text"]), match.end() + 100)
                excerpt = normalize_text(block["text"][start:end])
                if start > 0:
                    excerpt = "…" + excerpt
                if end < len(block["text"]):
                    excerpt += "…"
                found.append({"excerpt": excerpt, "source": block["source"]})
                break
    return found


def extract_skills(blocks: list[dict[str, str]]) -> list[dict[str, str]]:
    skills = []
    for canonical, aliases in SKILL_ALIASES.items():
        occurrences = find_occurrences(blocks, aliases)
        if occurrences:
            skills.append({
                "name": canonical,
                "evidence": "Repeated mention" if len(occurrences) > 1 else "Mention found",
                "excerpt": occurrences[0]["excerpt"],
                "source": occurrences[0]["source"],
            })
    return skills


def parse_requirements(raw: str, target_role: str) -> list[str]:
    raw = normalize_text(raw)
    if raw:
        segments = [segment.strip(" •\t-–—") for segment in re.split(r"[\n,;]+", raw) if segment.strip(" •\t-–—")]
        canonical: list[str] = []
        for segment in segments:
            matches = [name for name, aliases in SKILL_ALIASES.items() if any(contains_term(segment, alias) for alias in aliases)]
            if matches:
                canonical.extend(matches)
            else:
                shortened = re.sub(r"\s+", " ", segment).strip(" .")
                if 2 <= len(shortened) <= 100:
                    canonical.append(shortened)
        return list(dict.fromkeys(canonical))[:30]

    role = target_role.casefold()
    for role_aliases, criteria in ROLE_CRITERIA:
        if any(alias in role for alias in role_aliases):
            return list(criteria)
    return []


def criterion_occurrences(blocks: list[dict[str, str]], criterion: str) -> list[dict[str, str]]:
    aliases = SKILL_ALIASES.get(criterion, (criterion,))
    return find_occurrences(blocks, aliases)


def nearest_evidence(blocks: list[dict[str, str]], criterion: str) -> tuple[float, str, str]:
    """Use TF-IDF vectors and cosine similarity to find the nearest resume passage."""
    passages = [normalize_text(block["text"]) for block in blocks if len(block["text"].strip()) > 18]
    sources = [block["source"] for block in blocks if len(block["text"].strip()) > 18]
    if not passages:
        return 0.0, "", ""
    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
        matrix = vectorizer.fit_transform([*passages, criterion])
        model = NearestNeighbors(n_neighbors=1, metric="cosine", algorithm="brute")
        model.fit(matrix[:-1])
        distances, neighbors = model.kneighbors(matrix[-1])
        best_index = int(neighbors[0][0])
        similarity = max(0.0, 1.0 - float(distances[0][0]))
        return round(similarity * 100), passages[best_index][:300], sources[best_index]
    except ValueError:
        return 0.0, "", ""


def get_profile(blocks: list[dict[str, str]]) -> dict[str, str]:
    all_text = "\n".join(block["text"] for block in blocks)
    lines = [line.strip() for line in all_text.splitlines() if line.strip()]
    name = "Candidate"
    for line in lines[:8]:
        words = line.split()
        if not (1 < len(words) <= 4) or len(line) > 48:
            continue
        if re.search(r"[@\d:/\\]|https?://|resume|curriculum vitae|linkedin|github", line, re.I):
            continue
        if not all(any(char.isalpha() for char in word) for word in words):
            continue
        name = line.strip("|•- ")
        break
    years = re.search(r"(?i)(\d{1,2}(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)", all_text)
    if years:
        experience = f"{years.group(1)} years"
    else:
        years_after_label = re.search(r"(?i)(?:experience|professional experience)[^\n]{0,24}?(\d{1,2}(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", all_text)
        experience = f"{years_after_label.group(1)} years" if years_after_label else "Not detected"
    education = "Not detected"
    degree = re.search(r"(?i)\b(Ph\.?D\.?|M\.?Sc\.?|M\.?A\.?|M\.?Tech\.?|M\.?B\.?A\.?|B\.?Sc\.?|B\.?A\.?|B\.?Tech\.?|B\.?E\.?|B\.?Eng\.?|Bachelor(?:'s)?|Master(?:'s)?|Associate(?:'s)?)\b[^\n]{0,70}", all_text)
    if degree:
        education = normalize_text(degree.group(0))[:90]
    return {"name": name, "role": "Not detected", "experience": experience, "education": education, "location": "Not displayed"}


def analyze_blocks(blocks: list[dict[str, str]], target_role: str, requirements: str) -> dict[str, Any]:
    skills = extract_skills(blocks)
    criteria_names = parse_requirements(requirements, target_role)
    criteria = []
    for name in criteria_names:
        occurrences = criterion_occurrences(blocks, name)
        similarity, nearest_excerpt, nearest_source = nearest_evidence(blocks, name)
        mention_count = len(occurrences)
        # An explainable decision-tree-style triage supports review; it is not
        # a learned measure of skill proficiency or hiring probability.
        evidence_level = (
            "Repeated evidence" if mention_count >= 2 else
            "Direct mention" if mention_count == 1 else
            "Related passage" if similarity >= 12 else
            "No clear evidence"
        )
        criteria.append({
            "name": name,
            "found": bool(occurrences),
            "status": evidence_level,
            "detail": (f"{mention_count} direct mention(s); nearest text similarity {similarity}%.") if occurrences else (f"No exact mention; nearest text similarity {similarity}%.") ,
            "excerpt": occurrences[0]["excerpt"] if occurrences else (nearest_excerpt if similarity >= 12 else ""),
            "source": occurrences[0]["source"] if occurrences else (nearest_source if similarity >= 12 else ""),
            "similarity": similarity,
            "mentions": mention_count,
        })
    found_count = sum(item["found"] for item in criteria)
    total_count = len(criteria)
    fit = round(found_count / total_count * 100) if total_count else None
    summary = (
        f"Resume text supports {found_count} of {total_count} listed criteria. Review each excerpt for context."
        if total_count else "Add job requirements to calculate evidence coverage for this role."
    )
    return {
        **get_profile(blocks),
        "target_role": target_role,
        "fit": fit,
        "fit_status": f"{found_count} of {total_count} criteria" if total_count else "Add criteria",
        "summary": summary,
        "criteria_found": found_count,
        "criteria_total": total_count,
        "skills": skills,
        "criteria": criteria,
        "model_summary": {
            "knn": "TF-IDF + cosine nearest-passage matching",
            "decision_tree": "Explainable evidence triage using direct mention count and nearest-passage similarity",
            "validated_metrics": False,
            "metrics_note": "Accuracy, precision, recall, and F1 require a labeled evaluation dataset; they are not estimated from one resume.",
        },
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    """Extract readable PDF/DOCX text and return in-memory evidence matching."""
    if not request.target_role.strip():
        raise HTTPException(status_code=422, detail="Enter a target role.")
    blocks, _extension = decode_resume(request.filename, request.content_base64)
    return analyze_blocks(blocks, request.target_role.strip(), request.job_requirements)

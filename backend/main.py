"""EquiHire's session-only resume analysis API.

Uploaded content is accepted as JSON base64 and processed from memory. This
service deliberately has no database, file writes, logging of resume text, or
persistent upload directory.
"""

from __future__ import annotations

import base64
import binascii
import io
import os
import re
import shutil
import unicodedata
import zipfile
from collections import Counter
from typing import Any

import pymupdf as fitz
from docx import Document
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

MAX_RESUME_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARS = 300_000
MAX_PDF_PAGES = 150
MAX_OCR_PAGES = 8

app = FastAPI(
    title="EquiHire Analysis API",
    version="0.2.0",
    description="Session-only resume text extraction and evidence review API.",
)
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "EQUIHIRE_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class AnalyzeRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1, max_length=((MAX_RESUME_BYTES + 2) // 3) * 4)
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
    "C#": ("c#", "c sharp", "csharp"),
    "Go": ("golang", "go language"),
    "Rust": ("rust",),
    "Ruby": ("ruby",),
    "PHP": ("php",),
    "Swift": ("swift",),
    "Kotlin": ("kotlin",),
    "Scala": ("scala",),
    "R": ("r language", "r programming"),
    "Bash": ("bash", "shell scripting"),
    "PostgreSQL": ("postgresql", "postgres"),
    "MySQL": ("mysql",),
    "MongoDB": ("mongodb", "mongo db"),
    "Redis": ("redis",),
    "Apache Spark": ("apache spark", "pyspark", "spark"),
    "Hadoop": ("hadoop",),
    "Kubernetes": ("kubernetes", "k8s"),
    "Terraform": ("terraform",),
    "CI/CD": ("ci/cd", "continuous integration", "continuous delivery"),
    "Node.js": ("node.js", "nodejs", "node js"),
    "REST APIs": ("rest api", "rest apis", "restful api", "restful apis"),
    "FastAPI": ("fastapi",),
    "Figma": ("figma",),
    "Pandas": ("pandas",),
    "Linux": ("linux",),
    "User research": ("user research",),
    "Usability testing": ("usability testing", "usability test"),
    "Design systems": ("design system", "design systems"),
}

# Explainable skill profiles for common technology roles. This catalog creates
# role criteria; it does not claim to predict hiring outcomes.
ROLE_CRITERIA: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("data analyst", "data analytics analyst", "business data analyst", "data reporting analyst", "reporting analyst", "bi analyst", "business intelligence analyst"), ("SQL", "Excel", "Statistics", "Data visualization", "Python", "Tableau", "Power BI")),
    (("business analyst", "business systems analyst", "it business analyst"), ("SQL", "Excel", "Statistics", "Data visualization", "Python", "Power BI")),
    (("bi developer", "business intelligence developer", "power bi developer"), ("SQL", "Excel", "Statistics", "Data visualization", "Python", "Tableau", "Power BI")),
    (("product analyst", "product data analyst", "product analytics"), ("SQL", "Python", "A/B testing", "Statistics", "Tableau", "Data visualization")),
    (("data scientist", "data science", "applied data scientist"), ("Python", "SQL", "Statistics", "Machine learning", "scikit-learn", "Pandas", "Data visualization")),
    (("machine learning engineer", "ml engineer", "machine learning developer", "applied ml engineer", "ai/ml engineer", "ai ml engineer"), ("Python", "Machine learning", "scikit-learn", "TensorFlow", "PyTorch", "Docker", "AWS")),
    (("ai engineer", "artificial intelligence engineer", "generative ai engineer", "llm engineer", "llm application engineer", "ai platform engineer"), ("Python", "Machine learning", "PyTorch", "TensorFlow", "NLP", "REST APIs", "Docker")),
    (("data engineer", "big data engineer", "analytics engineer"), ("Python", "SQL", "AWS", "Azure", "Docker", "Git", "Pandas", "Apache Spark", "Hadoop")),
    (("data architect", "big data architect"), ("Python", "SQL", "AWS", "Azure", "Docker", "Data visualization")),
    (("data quality analyst", "data governance analyst"), ("SQL", "Python", "Excel", "Statistics", "Data visualization")),
    (("database administrator", "database admin", "database engineer", "dba"), ("SQL", "Python", "AWS", "Azure", "Docker", "Git")),
    (("frontend engineer", "front end engineer", "frontend developer", "front end developer", "frontend dev", "front end dev", "web developer"), ("JavaScript", "React", "HTML", "CSS", "TypeScript", "Git")),
    (("backend engineer", "back end engineer", "backend developer", "back end developer", "backend dev", "back end dev"), ("Python", "SQL", "REST APIs", "Docker", "Git", "AWS")),
    (("full stack engineer", "full stack developer", "fullstack developer", "fullstack engineer", "full stack dev"), ("JavaScript", "React", "HTML", "CSS", "TypeScript", "Python", "SQL", "REST APIs", "Git")),
    (("software engineer", "software developer", "application developer"), ("Python", "JavaScript", "SQL", "Git", "REST APIs", "Docker")),
    (("python developer", "python engineer", "python dev"), ("Python", "SQL", "REST APIs", "FastAPI", "Docker", "Git")),
    (("java developer", "java engineer", "java dev"), ("Java", "SQL", "REST APIs", "Docker", "Git", "AWS")),
    (("c++ developer", "cpp developer", "c++ engineer", "cpp engineer", "c++ dev", "cpp dev"), ("C++", "Git", "Linux", "Docker")),
    (("c# developer", "c sharp developer", "dotnet developer", ".net developer"), ("C#", "SQL", "REST APIs", "Docker", "Git", "Azure")),
    (("go developer", "golang developer", "go engineer", "golang engineer"), ("Go", "SQL", "REST APIs", "Docker", "Git", "Kubernetes")),
    (("rust developer", "rust engineer"), ("Rust", "Git", "Linux", "Docker")),
    (("ruby developer", "ruby on rails developer", "rails developer"), ("Ruby", "SQL", "REST APIs", "Docker", "Git")),
    (("php developer", "php engineer", "laravel developer"), ("PHP", "SQL", "REST APIs", "Docker", "Git", "MySQL")),
    (("swift developer", "ios software engineer"), ("Swift", "Git", "REST APIs")),
    (("kotlin developer", "android software engineer"), ("Kotlin", "Java", "Git", "REST APIs")),
    (("scala developer", "scala engineer"), ("Scala", "SQL", "Apache Spark", "Git")),
    (("r developer", "r programmer", "statistical programmer"), ("R", "Statistics", "SQL", "Data visualization")),
    (("devops engineer", "site reliability engineer", "sre", "platform engineer"), ("AWS", "Azure", "Docker", "Git", "Python", "Linux", "Kubernetes", "Terraform", "CI/CD")),
    (("cloud engineer", "cloud developer", "cloud architect"), ("AWS", "Azure", "Docker", "Python", "Git", "Kubernetes", "Terraform")),
    (("cybersecurity analyst", "security analyst", "information security analyst"), ("Python", "SQL", "AWS", "Azure", "Linux", "Git")),
    (("security engineer", "application security engineer", "penetration tester", "penetration testing engineer"), ("Python", "JavaScript", "SQL", "AWS", "Linux", "Git")),
    (("qa engineer", "quality assurance engineer", "software tester", "test engineer"), ("Python", "JavaScript", "SQL", "Git", "REST APIs")),
    (("automation test engineer", "test automation engineer", "sdet", "qa automation engineer"), ("Python", "JavaScript", "SQL", "Git", "Docker")),
    (("mobile developer", "mobile engineer", "android developer", "ios developer"), ("Java", "Python", "JavaScript", "Git", "REST APIs")),
    (("react developer", "react engineer", "react dev"), ("JavaScript", "React", "HTML", "CSS", "TypeScript", "Git")),
    (("javascript developer", "javascript engineer", "typescript developer"), ("JavaScript", "TypeScript", "HTML", "CSS", "React", "Node.js", "Git")),
    (("node developer", "node.js developer", "nodejs developer"), ("Node.js", "JavaScript", "TypeScript", "REST APIs", "SQL", "Docker", "Git")),
    (("cloud data engineer", "etl developer", "etl engineer"), ("Python", "SQL", "AWS", "Azure", "Docker", "Git")),
    (("nlp engineer", "natural language processing engineer", "computer vision engineer"), ("Python", "Machine learning", "NLP", "PyTorch", "TensorFlow", "scikit-learn")),
    (("research scientist", "research engineer", "applied scientist"), ("Python", "Statistics", "Machine learning", "PyTorch", "TensorFlow", "scikit-learn")),
    (("ux designer", "product designer", "user experience designer"), ("Figma", "User research", "Usability testing", "Design systems")),
    (("product manager", "technical product manager"), ("SQL", "Statistics", "A/B testing", "Data visualization", "Figma")),
    (("technical writer", "documentation engineer"), ("Python", "JavaScript", "Git", "REST APIs")),
    (("it support", "technical support engineer", "systems administrator", "system administrator"), ("Python", "SQL", "AWS", "Azure", "Linux", "Git")),
    (("teacher",), ("Python", "Statistics", "Data visualization")),
    (("finance",), ("Excel", "SQL", "Statistics", "Data visualization")),
    (("apparel",), ("Excel", "Statistics", "Data visualization")),
    (("accountant", "accounting"), ("Excel", "SQL", "Statistics")),
    (("banking",), ("Excel", "SQL", "Statistics")),
    (("research assistant",), ("Python", "Statistics", "Machine learning")),
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
            ocr_pages = 0
            can_ocr = shutil.which("tesseract") is not None
            for index, page in enumerate(pdf):
                page_blocks = page.get_text("blocks", sort=True)
                parts = [
                    block[4].strip()
                    for block in page_blocks
                    if len(block) > 4 and isinstance(block[4], str) and block[4].strip()
                ]
                text = normalize_text("\n".join(parts))
                source = f"PDF · p. {index + 1}"
                if len(text) < 50 and page.get_images(full=True) and can_ocr and ocr_pages < MAX_OCR_PAGES:
                    try:
                        text_page = page.get_textpage_ocr(language="eng", dpi=220, full=True)
                        ocr_blocks = page.get_text("blocks", textpage=text_page, sort=True)
                        ocr_parts = [
                            block[4].strip()
                            for block in ocr_blocks
                            if len(block) > 4 and isinstance(block[4], str) and block[4].strip()
                        ]
                        ocr_text = normalize_text("\n".join(ocr_parts))
                        ocr_pages += 1
                        if len(ocr_text) > len(text):
                            text = ocr_text
                            source += " · OCR"
                    except Exception:
                        # Keep the original extraction and return a quality warning later.
                        pass
                if text:
                    blocks.append({"text": text, "source": source})
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
        for section_index, section in enumerate(document.sections, start=1):
            for label, container in (("header", section.header), ("footer", section.footer)):
                lines = [normalize_text(paragraph.text) for paragraph in container.paragraphs]
                lines = [line for line in lines if line]
                if lines:
                    blocks.append({"text": "\n".join(lines), "source": f"DOCX · {label} {section_index}"})
                for table_index, table in enumerate(container.tables, start=1):
                    for row_index, row in enumerate(table.rows, start=1):
                        text = normalize_text(" | ".join(cell.text for cell in row.cells))
                        if text:
                            blocks.append({"text": text, "source": f"DOCX · {label} {section_index}, table {table_index}, row {row_index}"})
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
        raise HTTPException(status_code=422, detail="No readable text was found. The PDF may be scanned or password protected; check that it opens normally and contains legible text.")
    return blocks, extension


def contains_term(text: str, term: str) -> bool:
    pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def count_mentions(blocks: list[dict[str, str]], aliases: tuple[str, ...]) -> int:
    """Count direct mentions without returning resume snippets or contact text."""
    total = 0
    for block in blocks:
        for alias in aliases:
            matches = re.findall(rf"(?<!\w){re.escape(alias)}(?!\w)", block["text"], flags=re.IGNORECASE)
            if matches:
                total += len(matches)
                break
    return total


def extract_skills(blocks: list[dict[str, str]]) -> list[dict[str, Any]]:
    skills = []
    for canonical, aliases in SKILL_ALIASES.items():
        mentions = count_mentions(blocks, aliases)
        if mentions:
            sources = [
                block["source"] for block in blocks
                if any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", block["text"], re.IGNORECASE) for alias in aliases)
            ]
            skills.append({"name": canonical, "mentions": mentions, "sources": list(dict.fromkeys(sources))})
    return skills

def parse_requirements(raw: str, target_role: str) -> list[str]:
    raw = normalize_text(raw)
    if raw:
        # Search the whole pasted job description first so skills are found
        # even when they appear inside longer sentences rather than a list.
        recognized = [
            name
            for name, aliases in SKILL_ALIASES.items()
            if any(contains_term(raw, alias) for alias in aliases)
        ]
        if recognized:
            return recognized[:30]
        segments = [
            segment.strip(" •\t-–—")
            for segment in re.split(r"[\n,;|•]+", raw)
            if segment.strip(" •\t-–—")
        ]
        custom = []
        for segment in segments:
            shortened = re.sub(r"\s+", " ", segment).strip(" .")
            if 2 <= len(shortened) <= 100:
                custom.append(shortened)
        if custom:
            return list(dict.fromkeys(custom))[:30]

    role_aliases = [alias for aliases, _ in ROLE_CRITERIA for alias in aliases]
    canonical_role = normalize_role(target_role, role_aliases)
    for aliases, criteria in ROLE_CRITERIA:
        if canonical_role.casefold() in aliases:
            return list(criteria)
    return []

def normalize_role(value: str, aliases: list[str] | None = None) -> str:
    """Resolve role aliases and common one- or two-character typing mistakes."""
    from difflib import SequenceMatcher

    role = re.sub(r"[^a-z0-9+#.]+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()
    role = re.sub(r"\s+", " ", role)
    role = re.sub(r"\bdev\b", "developer", role)
    role = re.sub(r"\beng\b", "engineer", role)
    role = re.sub(r"\bsr\b", "senior", role)
    role = re.sub(r"\bjr\b", "junior", role)
    role_tokens = set(role.split()) - {"senior", "junior", "lead", "staff", "principal"}
    aliases = aliases or [alias for role_aliases, _ in ROLE_CRITERIA for alias in role_aliases]
    normalized = [
        (alias, re.sub(r"[^a-z0-9+#.]+", " ", alias.casefold()).strip())
        for alias in aliases
    ]

    scored = []
    for alias, candidate in normalized:
        candidate_tokens = set(candidate.split())
        exact_coverage = len(role_tokens & candidate_tokens) / max(1, len(candidate_tokens))
        fuzzy_matches = 0
        for candidate_token in candidate_tokens:
            if candidate_token in role_tokens:
                fuzzy_matches += 1
                continue
            if len(candidate_token) < 5:
                continue
            best_token_ratio = max(
                (SequenceMatcher(None, candidate_token, typed_token).ratio()
                 for typed_token in role_tokens if len(typed_token) >= 4
                 and abs(len(candidate_token) - len(typed_token)) <= 2),
                default=0.0,
            )
            if best_token_ratio >= 0.72:
                fuzzy_matches += 1
        fuzzy_coverage = fuzzy_matches / max(1, len(candidate_tokens))
        phrase_ratio = SequenceMatcher(None, role, candidate).ratio()
        score = max(phrase_ratio, exact_coverage * 0.92, fuzzy_coverage * 0.86)
        scored.append((score, alias))

    best_score, best_alias = max(scored, default=(0.0, ""))
    if best_score < 0.76:
        return role
    display = best_alias.title()
    for short, canonical in (
        ("Ai Ml ", "AI/ML "), ("Ai/Ml ", "AI/ML "),
        ("Ml ", "ML "), ("Ai ", "AI "),
        ("Ux ", "UX "), ("Ui ", "UI "), ("Qa ", "QA "),
        ("Bi ", "BI "), ("It ", "IT "), ("Cpp ", "C++ "),
    ):
        display = display.replace(short, canonical)
    return display


def nearest_evidence_similarity(blocks: list[dict[str, str]], criterion: str) -> int:
    """Score the closest text passage without returning its contents."""
    passages = [normalize_text(block["text"]) for block in blocks if len(block["text"].strip()) > 18]
    if not passages:
        return 0
    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
        matrix = vectorizer.fit_transform([*passages, criterion])
        model = NearestNeighbors(n_neighbors=1, metric="cosine", algorithm="brute")
        model.fit(matrix[:-1])
        distances, _ = model.kneighbors(matrix[-1])
        return round(max(0.0, 1.0 - float(distances[0][0])) * 100)
    except ValueError:
        return 0

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


def suggest_career_directions(skills: list[dict[str, Any]], experience: str) -> list[dict[str, Any]]:
    """Rank explainable role suggestions from resume skill mentions only."""
    present = {item["name"] for item in skills}
    if not present:
        return []

    # Keep one readable role title per profile and skip broad catch-all labels.
    excluded = {"teacher", "finance", "apparel", "accountant", "banking", "research assistant"}
    ranked = []
    seen_titles = set()
    for aliases, required in ROLE_CRITERIA:
        title = aliases[0].title()
        for short, canonical in (("Ai/Ml", "AI/ML"), ("Ai ", "AI "), ("Ml ", "ML "), ("Bi ", "BI "), ("Ux ", "UX "), ("Ui ", "UI "), ("Qa ", "QA "), ("It ", "IT "), ("Cpp", "C++")):
            title = title.replace(short, canonical)
        if title.casefold() in excluded or title.casefold() in seen_titles:
            continue
        seen_titles.add(title.casefold())
        matched = [skill for skill in required if skill in present]
        if not matched:
            continue
        # Coverage is based on detected mentions, never on inferred proficiency.
        score = round(len(matched) / len(required) * 100)
        missing = [skill for skill in required if skill not in present]
        ranked.append({
            "role": title,
            "match": score,
            "matched_skills": matched,
            "next_skills": missing,
            "required_count": len(required),
            "reason": f"{len(matched)} of {len(required)} profile skills appear in the resume.",
            "experience_context": experience,
        })
    ranked.sort(key=lambda item: (item["match"], len(item["matched_skills"])), reverse=True)
    return ranked[:4]


def analyze_blocks(blocks: list[dict[str, str]], target_role: str, requirements: str) -> dict[str, Any]:
    criteria_names = parse_requirements(requirements, target_role)
    skills = extract_skills(blocks)
    for skill in skills:
        skill["role_match"] = skill["name"] in criteria_names
    criteria = []
    for name in criteria_names:
        mention_count = count_mentions(blocks, SKILL_ALIASES.get(name, (name,)))
        similarity = nearest_evidence_similarity(blocks, name)
        # Transparent rules support review; they are not a learned measure of
        # skill proficiency or hiring probability.
        evidence_level = (
            "Repeated evidence" if mention_count >= 2 else
            "Direct mention" if mention_count == 1 else
            "Related passage" if similarity >= 12 else
            "No clear evidence"
        )
        criteria.append({
            "name": name,
            "found": mention_count > 0,
            "status": evidence_level,
            "detail": (f"{mention_count} direct mention(s); nearest text similarity {similarity}%.") if mention_count else (f"No exact mention; nearest text similarity {similarity}%.") ,
            "similarity": similarity,
            "mentions": mention_count,
        })
    found_count = sum(item["found"] for item in criteria)
    total_count = len(criteria)
    fit = round(found_count / total_count * 100) if total_count else None
    summary = (
        f"Resume text supports {found_count} of {total_count} listed criteria. Review each criterion against the original resume."
        if total_count else "Add job requirements to calculate evidence coverage for this role."
    )
    try:
        from ml.predict import predict_role_relevance
        model_relevance = predict_role_relevance(target_role, "\n".join(block["text"] for block in blocks))
    except (OSError, ValueError):
        model_relevance = None
    return {
        **get_profile(blocks),
        "target_role": target_role,
        "fit": fit,
        "fit_status": f"{found_count} of {total_count} criteria" if total_count else "Add criteria",
        "summary": summary,
        "normalized_role": normalize_role(target_role),
        "criteria_found": found_count,
        "criteria_total": total_count,
        "skills": skills,
        "criteria": criteria,
        "career_directions": suggest_career_directions(skills, get_profile(blocks)["experience"]),
        "model_summary": {
            "knn": "TF-IDF + cosine nearest-passage matching",
            "decision_tree": "TF-IDF relevance-score regression trained on public expert annotations, when the role is supported",
            "model_relevance": model_relevance,
            "model_target": "Broad expert-assessed role-category relevance from CareerCorpus; not hiring probability or skill proficiency.",
        },
    }


@app.get("/demo")
def demo() -> dict[str, Any]:
    """Return a synthetic resume analysis for a quick UI walkthrough."""
    blocks = [
        {"text": "Jordan Lee\nData Analyst\n3 years of experience\nBachelor of Science in Information Systems", "source": "SAMPLE RESUME · profile"},
        {"text": "Built SQL queries and Python scripts to clean sales data and create repeatable reporting workflows.", "source": "SAMPLE RESUME · experience"},
        {"text": "Created Power BI dashboards and Excel reports; used statistics to explain weekly changes to stakeholders.", "source": "SAMPLE RESUME · projects"},
    ]
    result = analyze_blocks(blocks, "Data Analyst", "SQL, Python, Power BI, Tableau")
    result["extraction"] = {"format": "SAMPLE", "characters": sum(len(block["text"]) for block in blocks), "ocr_pages": 0, "warnings": ["Synthetic demo profile; not a real person or resume."]}
    return result


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "equihire-analysis", "version": app.version}


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    """Extract readable PDF/DOCX text and return in-memory evidence matching."""
    if not request.target_role.strip():
        raise HTTPException(status_code=422, detail="Enter a target role.")
    blocks, extension = decode_resume(request.filename, request.content_base64)
    result = analyze_blocks(blocks, request.target_role.strip(), request.job_requirements)
    extracted_characters = sum(len(block["text"]) for block in blocks)
    warnings = []
    ocr_pages = sum("OCR" in block["source"] for block in blocks)
    if extracted_characters < 250:
        warnings.append("Very little text was extracted. Check the preview and confirm the resume is readable.")
    result["extraction"] = {
        "format": extension.upper(),
        "characters": extracted_characters,
        "text_blocks": len(blocks),
        "ocr_pages": ocr_pages,
        "warnings": warnings,
    }
    return result

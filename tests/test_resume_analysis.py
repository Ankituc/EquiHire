from __future__ import annotations

import base64
import io
import shutil

import pymupdf as fitz
import pytest
from docx import Document
from fastapi import HTTPException

from backend.main import (
    analyze_blocks,
    count_mentions,
    decode_resume,
    extract_docx,
    extract_pdf,
    parse_requirements,
)


def make_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((48, 72), text, fontsize=14)
    data = document.tobytes()
    document.close()
    return data


def encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_pdf_extraction_and_typed_role_analysis():
    data = make_pdf("Jordan Lee\nData Analyst\nSQL, Python, pandas, Power BI")
    blocks = extract_pdf(data)
    result = analyze_blocks(blocks, "Data ANlsyt", "")
    assert "Power BI" in "\n".join(block["text"] for block in blocks)
    assert result["normalized_role"] == "Data Analyst"
    assert result["criteria_total"] > 0
    assert any(skill["name"] == "SQL" and skill["role_match"] for skill in result["skills"])
    assert all("excerpt" not in item and "source" not in item for item in result["criteria"])


def test_docx_extracts_paragraphs_tables_headers_and_footers():
    document = Document()
    document.sections[0].header.paragraphs[0].text = "Resume header"
    document.add_paragraph("Python developer with FastAPI experience")
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Projects: PostgreSQL, Docker"
    document.sections[0].footer.paragraphs[0].text = "Resume footer"
    data = io.BytesIO()
    document.save(data)
    blocks = extract_docx(data.getvalue())
    combined = "\n".join(block["text"] for block in blocks)
    assert all(value in combined for value in ("Python", "PostgreSQL", "Resume header", "Resume footer"))


def test_long_job_description_extracts_known_skills():
    description = "We need an analyst to build reliable reports and dashboards. The role requires SQL, Python, and Power BI skills."
    criteria = parse_requirements(description, "Data Analyst")
    assert criteria == ["Python", "SQL", "Power BI"]


def test_mention_count_does_not_return_resume_text():
    blocks = [{"text": "Python and Python; Python developer", "source": "PDF · p. 1"}]
    assert count_mentions(blocks, ("python",)) == 3


def test_decode_rejects_fake_pdf_content():
    with pytest.raises(HTTPException) as error:
        decode_resume("resume.pdf", encode(b"not a pdf"))
    assert error.value.status_code == 415


def test_decode_rejects_invalid_base64():
    with pytest.raises(HTTPException) as error:
        decode_resume("resume.pdf", "%%%invalid%%")
    assert error.value.status_code == 400


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract OCR is not installed")
def test_image_only_pdf_uses_optional_ocr():
    source = fitz.open()
    source_page = source.new_page(width=595, height=842)
    source_page.insert_text((48, 90), "OCR CHECK\nPython developer\nSQL and Docker projects", fontsize=24, lineheight=1.7)
    image_data = source_page.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png")
    scanned = fitz.open()
    scanned_page = scanned.new_page(width=595, height=842)
    scanned_page.insert_image(scanned_page.rect, stream=image_data)
    data = scanned.tobytes()
    source.close()
    scanned.close()

    blocks = extract_pdf(data)
    extracted = "\n".join(block["text"] for block in blocks)
    assert any("OCR" in block["source"] for block in blocks)
    assert "python" in extracted.casefold()

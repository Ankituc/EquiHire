import base64

import pymupdf as fitz
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def make_resume_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((48, 72), "Jordan Lee\nData Analyst\nSQL, Python, Power BI", fontsize=14)
    content = document.tobytes()
    document.close()
    return content


def test_upload_api_returns_extracted_resume_analysis():
    response = client.post(
        "/analyze",
        json={
            "filename": "sample-resume.pdf",
            "content_base64": base64.b64encode(make_resume_pdf()).decode("ascii"),
            "target_role": "Data ANlsyt",
            "job_requirements": "SQL, Python, Power BI",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["normalized_role"] == "Data Analyst"
    assert result["extraction"]["format"] == "PDF"
    assert result["extraction"]["characters"] > 0
    assert result["criteria_total"] == 3
    assert result["criteria_found"] == 3
    assert {skill["name"] for skill in result["skills"]} >= {"SQL", "Python", "Power BI"}
    assert all("excerpt" not in criterion and "source" not in criterion for criterion in result["criteria"])

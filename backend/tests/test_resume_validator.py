import pytest
from unittest.mock import patch, MagicMock
from utils.resume_validator import validate_resume


def mock_pdf(spans):
    mock_doc = MagicMock()
    mock_page = MagicMock()

    mock_page.get_text.return_value = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": spans
                    }
                ]
            }
        ]
    }

    mock_doc.__iter__.return_value = [mock_page]
    return mock_doc


@patch("utils.resume_validator.fitz.open")
def test_clean_resume(mock_fitz):
    spans = [{
        "text": "Experienced Python developer with cloud knowledge",
        "size": 12,
        "color": 0
    }]

    mock_fitz.return_value = mock_pdf(spans)

    jobs_data = [{"id": 1, "text": "Cloud architect role"}]

    issues = validate_resume("fake.pdf", jobs_data)

    assert issues == []


@patch("utils.resume_validator.fitz.open")
def test_small_font_detected(mock_fitz):
    spans = [{
        "text": "This is a hidden copied job description text",
        "size": 4,
        "color": 0
    }]

    mock_fitz.return_value = mock_pdf(spans)

    jobs_data = [{"id": 1, "text": "Random job"}]

    issues = validate_resume("fake.pdf", jobs_data)

    assert "Very small font detected" in issues


@patch("utils.resume_validator.fitz.open")
def test_white_text_detected(mock_fitz):
    spans = [{
        "text": "Invisible white colored job description text here",
        "size": 12,
        "color": 16777215
    }]

    mock_fitz.return_value = mock_pdf(spans)

    jobs_data = [{"id": 1, "text": "Random job"}]

    issues = validate_resume("fake.pdf", jobs_data)

    assert "Invisible/white colored text detected" in issues


@patch("utils.resume_validator.fitz.open")
def test_job_copy_detected(mock_fitz):
    job_text = "Cloud architect responsible for AWS deployment and scaling"

    spans = [{
        "text": job_text,
        "size": 12,
        "color": 0
    }]

    mock_fitz.return_value = mock_pdf(spans)

    jobs_data = [{"id": 99, "text": job_text}]

    issues = validate_resume("fake.pdf", jobs_data)

    assert "Copied job description from job id 99" in issues


@patch("utils.resume_validator.fitz.open")
def test_no_text_scanned_pdf(mock_fitz):
    spans = [{
        "text": "",
        "size": 12,
        "color": 0
    }]

    mock_fitz.return_value = mock_pdf(spans)

    jobs_data = [{"id": 1, "text": "Something"}]

    issues = validate_resume("fake.pdf", jobs_data)

    assert "No extractable text (possibly scanned PDF)" in issues


@patch("utils.resume_validator.fitz.open")
def test_multiple_issues(mock_fitz):
    job_text = "This is a hidden copied job description text"

    spans = [{
        "text": job_text,
        "size": 4,
        "color": 16777215
    }]

    mock_fitz.return_value = mock_pdf(spans)

    jobs_data = [{"id": 1, "text": job_text}]

    issues = validate_resume("fake.pdf", jobs_data)

    assert "Very small font detected" in issues
    assert "Invisible/white colored text detected" in issues
    assert "Copied job description from job id 1" in issues
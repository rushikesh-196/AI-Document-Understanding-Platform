import json
import io
import fitz
from docx import Document
from services.export_service import export_to_pdf, export_to_docx, export_to_json, export_to_csv

def test_export_to_pdf_and_docx_page_breaks():
    sample_job = {
        "job_id": "TEST-JOB-123",
        "filename": "invoice_sample.pdf",
        "document_type": "Invoice",
        "confidence_score": "98.5%",
        "timestamp": "2026-08-09 12:00:00",
        "summary": "This is an invoice document for test verification.",
        "extracted_fields": [
            {"field_name": "Invoice Number", "value": "INV-2026-001", "confidence": "99%"},
            {"field_name": "Total Amount", "value": "$1,480.00", "confidence": "100%"}
        ],
        "entities": [
            {"label": "Organization", "value": "Acme Corp"}
        ],
        "layout_analysis": {
            "headings": ["Invoice", "Items"],
            "forms_detected": True,
            "tables_detected": False
        },
        "raw_text": "Sample Invoice Header\nLine 1: Item 1\nLine 2: Item 2\nLine 3: Total $1480.00"
    }

    # Test PDF
    pdf_bytes = export_to_pdf(sample_job)
    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert len(pdf_doc) >= 2
    assert "INTELLIGENT OCR EXTRACTION REPORT" in pdf_doc[0].get_text()
    assert "RAW EXTRACTED TEXT" in pdf_doc[1].get_text()

    # Test DOCX
    docx_bytes = export_to_docx(sample_job)
    doc = Document(io.BytesIO(docx_bytes))
    full_text = "\n".join([p.text for p in doc.paragraphs])
    assert "Intelligent OCR Extraction Report" in full_text
    assert "Raw Extracted Text" in full_text

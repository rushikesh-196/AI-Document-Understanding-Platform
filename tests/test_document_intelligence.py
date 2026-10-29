import re

from services.document_intelligence import build_document_analysis, build_ai_json_output


def test_build_document_analysis_returns_structured_output():
    sample_text = """
    Invoice
    Invoice #INV-1001
    Date: 2026-08-01
    Customer: John Doe
    Company: Acme Solutions
    Total Amount: $1,480.00
    GST Number: 27ABCDE1234F1Z5
    """

    result = build_document_analysis(sample_text, filename="invoice_sample.pdf")

    assert result["document_type"] == "Invoice"
    assert any(item["field_name"] == "Total Amount" for item in result["extracted_fields"])
    assert any(item["field_name"] == "Company" for item in result["extracted_fields"])
    assert any(item["field_name"] == "Date" for item in result["extracted_fields"])
    assert isinstance(result["layout_analysis"], dict)
    assert "invoice" in result["summary"].lower()
    assert isinstance(result["tables"], list)


def test_build_document_analysis_generates_multi_sentence_summary():
    sample_text = """
    Electricity Bill
    Customer: Rahul Sharma
    Account Number: 9876543210
    Due Date: 2026-06-25
    Total Amount: ₹4,250.50
    Billing Address: 12, Sector 15, Pune
    """

    result = build_document_analysis(sample_text, filename="bill_sample.pdf")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", result["summary"]) if s.strip()]

    assert len(sentences) >= 2
    assert "bill" in result["summary"].lower() or "receipt" in result["summary"].lower() or "document" in result["summary"].lower()
    assert "rahul" in result["summary"].lower() or "amount" in result["summary"].lower() or "payment" in result["summary"].lower()


def test_build_ai_json_output_uses_document_specific_schema():
    payload = build_ai_json_output(
        document_type="Invoice",
        filename="invoice_sample.pdf",
        summary="Invoice issued by ABC Pvt Ltd for office supplies.",
        confidence_score=98.4,
        extracted_fields=[
            {"field_name": "Invoice Number", "field_key": "invoice_number", "value": "INV-2026-001"},
            {"field_name": "Total Amount", "field_key": "total_amount", "value": "12500"},
            {"field_name": "Company", "field_key": "company", "value": "ABC Pvt Ltd"},
        ],
        structured_data={
            "invoice_number": "INV-2026-001",
            "vendor_name": "ABC Pvt Ltd",
            "customer_name": "XYZ Solutions",
            "total_amount": 12500,
            "currency": "INR",
            "gst_number": None,
        },
        tables=[{"row": "Office Chair | 2 | 4500"}, {"row": "Keyboard | 1 | 3500"}],
    )

    assert payload["document_type"] == "Invoice"
    assert payload["filename"] == "invoice_sample.pdf"
    assert payload["overall_confidence"] == 98.4
    assert payload["extracted_fields"]["invoice_number"] == "INV-2026-001"
    assert "gst_number" not in payload["extracted_fields"]
    assert payload["tables"] == ["Office Chair | 2 | 4500", "Keyboard | 1 | 3500"]
    assert payload["ai_summary"] == "Invoice issued by ABC Pvt Ltd for office supplies."
    assert "engine" not in payload

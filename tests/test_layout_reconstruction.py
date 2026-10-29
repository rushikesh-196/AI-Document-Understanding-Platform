import json
import os

from services.layout_reconstruction import (
    build_char_grid,
    parse_block_items,
    reconstruct_document,
    reconstruct_document_html,
    reconstruct_page,
    smart_text_reconstruct,
)


FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "extracted",
    "JOB-89DC7042.json",
)


def _load_fixture():
    if os.path.exists(FIXTURE_PATH):
        with open(FIXTURE_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    return {
        "page_layouts": [{
            "page": 1,
            "image_width": 600,
            "image_height": 800,
            "blocks": [
                {"text": "SHOPNAME", "bbox": {"x_min": 250, "y_min": 40, "x_max": 350, "y_max": 60}, "is_heading": True},
                {"text": "CASH RECEIPT", "bbox": {"x_min": 230, "y_min": 75, "x_max": 370, "y_max": 95}, "is_heading": True},
                {"text": "Description", "bbox": {"x_min": 40, "y_min": 140, "x_max": 140, "y_max": 160}, "is_heading": False},
                {"text": "Price", "bbox": {"x_min": 460, "y_min": 140, "x_max": 510, "y_max": 160}, "is_heading": False},
                {"text": "Lorem", "bbox": {"x_min": 40, "y_min": 180, "x_max": 100, "y_max": 200}, "is_heading": False},
                {"text": "1.1", "bbox": {"x_min": 460, "y_min": 180, "x_max": 490, "y_max": 200}, "is_heading": False},
                {"text": "Total", "bbox": {"x_min": 40, "y_min": 240, "x_max": 90, "y_max": 260}, "is_heading": False},
                {"text": "1.1", "bbox": {"x_min": 460, "y_min": 240, "x_max": 490, "y_max": 260}, "is_heading": False},
                {"text": "THANK YOU", "bbox": {"x_min": 240, "y_min": 310, "x_max": 360, "y_max": 330}, "is_heading": False},
            ]
        }]
    }


def test_reconstruct_page_preserves_column_layout_from_blocks():
    job = _load_fixture()
    page = job["page_layouts"][0]
    output = reconstruct_page(page)

    assert "SHOPNAME" in output
    assert "CASH RECEIPT" in output or "CASHRECEIPT" in output.replace(" ", "")
    assert "Description" in output
    assert "Price" in output
    assert "Lorem" in output
    assert "1.1" in output
    assert "Total" in output
    assert "THANK YOU" in output or "THANKYOU" in output.replace(" ", "")

    desc_idx = output.find("Description")
    price_idx = output.find("Price")
    assert desc_idx != -1 and price_idx != -1
    assert desc_idx < price_idx


def test_reconstruct_page_does_not_flatten_label_value_pairs():
    sample_blocks = [
        {
            "text": "Name:",
            "bbox": {"x_min": 50, "y_min": 100, "x_max": 120, "y_max": 120},
            "is_heading": False,
        },
        {
            "text": "John Doe",
            "bbox": {"x_min": 130, "y_min": 100, "x_max": 250, "y_max": 120},
            "is_heading": False,
        },
        {
            "text": "DOB:",
            "bbox": {"x_min": 50, "y_min": 140, "x_max": 120, "y_max": 160},
            "is_heading": False,
        },
        {
            "text": "12/03/1998",
            "bbox": {"x_min": 130, "y_min": 140, "x_max": 250, "y_max": 160},
            "is_heading": False,
        },
    ]
    items = parse_block_items(sample_blocks)
    output = build_char_grid(items, 800, 1000)

    assert "Name:" in output
    assert "John Doe" in output
    assert "DOB:" in output
    assert "12/03/1998" in output
    assert output.index("Name:") < output.index("John Doe")
    assert output.index("DOB:") < output.index("12/03/1998")


def test_reconstruct_document_multi_page_includes_page_separators():
    pages = [
        {
            "page": 1,
            "text": "Page One Header",
            "blocks": [
                {
                    "text": "Page One Header",
                    "bbox": {"x_min": 100, "y_min": 50, "x_max": 300, "y_max": 80},
                    "is_heading": True,
                }
            ],
            "image_width": 800,
            "image_height": 1000,
        },
        {
            "page": 2,
            "text": "Page Two Header",
            "blocks": [
                {
                    "text": "Page Two Header",
                    "bbox": {"x_min": 100, "y_min": 50, "x_max": 300, "y_max": 80},
                    "is_heading": True,
                }
            ],
            "image_width": 800,
            "image_height": 1000,
        },
    ]

    output = reconstruct_document(page_layouts=pages)
    assert "PAGE 1" in output
    assert "PAGE 2" in output
    assert "Page One Header" in output
    assert "Page Two Header" in output


def test_reconstruct_page_uses_word_boxes_for_column_alignment():
    """Word-level boxes produce finer column spacing than line-level blocks."""
    page = {
        "text": "Item Qty Price\nMilk 2 4.50",
        "word_boxes": [
            {"text": "Item", "box": [[50, 100], [90, 100], [90, 120], [50, 120]]},
            {"text": "Qty", "box": [[300, 100], [340, 100], [340, 120], [300, 120]]},
            {"text": "Price", "box": [[450, 100], [500, 100], [500, 120], [450, 120]]},
            {"text": "Milk", "box": [[50, 130], [90, 130], [90, 150], [50, 150]]},
            {"text": "2", "box": [[310, 130], [330, 130], [330, 150], [310, 150]]},
            {"text": "4.50", "box": [[450, 130], [490, 130], [490, 150], [450, 150]]},
        ],
        "image_width": 600,
        "image_height": 800,
    }
    output = reconstruct_page(page)

    assert "Item" in output
    assert "Qty" in output
    assert "Price" in output
    assert "Milk" in output
    assert "4.50" in output
    item_idx = output.find("Item")
    qty_idx = output.find("Qty")
    price_idx = output.find("Price")
    assert item_idx < qty_idx < price_idx


def test_smart_text_reconstruct_preserves_headings_and_blank_lines():
    raw = "INVOICE\n\nCompany Name    Invoice Number\nABC Company     INV-001\n"
    output = smart_text_reconstruct(raw)

    assert "INVOICE" in output
    assert "Company Name" in output
    assert "Invoice Number" in output
    assert "ABC Company" in output
    assert "INV-001" in output


def test_reconstruct_document_html_produces_real_table():
    """reconstruct_document_html should output proper HTML <table> markup
    and never emit raw '|' pipe separators in text nodes."""
    pages = [
        {
            "page": 1,
            "text": (
                "RECEIPT\n"
                "Receipt Date : January 15, 2050\n"
                "Patient Name : John Doe\n"
                "Description | Qty | Amount\n"
                "Consultation | 1 | $150.00\n"
                "Lab Test | 2 | $80.00\n"
                "Total Amount Due : $230.00\n"
            ),
            "blocks": [],
            "word_boxes": [],
            "image_width": 800,
            "image_height": 1000,
        }
    ]
    raw_text = pages[0]["text"]

    html = reconstruct_document_html(
        page_layouts=pages,
        raw_text=raw_text,
        bounding_boxes=[],
        structured_data={},
        tables=[],
        doc_type="receipt",
    )

    assert isinstance(html, str)
    assert len(html) > 0

    # Must use real HTML table — no ASCII box fallback
    assert "<table" in html.lower()

    # Must NOT contain raw pipe separators in rendered text
    import re
    text_only = re.sub(r"<[^>]+>", " ", html)
    assert "|" not in text_only, "Raw '|' pipe found in HTML text nodes"

    # Key field values must appear
    assert "John Doe" in html

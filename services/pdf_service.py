"""
PDF Processing & Direct Vector Text Extraction Service
Optimized for instant native extraction and fast rendering.
"""

import io
from PIL import Image


def extract_pdf_native_text(pdf_path):
    """
    Extracts embedded vector text directly from PDF pages if available.
    Returns string of raw text or empty string if scanned/image-only.
    """
    text_content = []
    try:
        import fitz
        doc = fitz.open(pdf_path)
        for page in doc:
            txt = page.get_text().strip()
            if txt:
                text_content.append(txt)
        doc.close()
    except Exception:
        pass

    return "\n\n".join(text_content).strip()


def extract_pdf_native_blocks(pdf_path):
    """
    Extract structured layout blocks directly from native PDF pages without OCR.
    Returns list of page layout dicts or empty list if scanned.
    """
    page_layouts = []
    try:
        import fitz
        doc = fitz.open(pdf_path)
        for page_idx, page in enumerate(doc):
            rect = page.rect
            width, height = rect.width, rect.height
            blocks_raw = page.get_text("blocks")
            blocks = []
            page_lines = []

            for b in blocks_raw:
                # b format: (x0, y0, x1, y1, "text", block_no, block_type)
                if len(b) >= 5 and b[4].strip():
                    text = b[4].strip()
                    page_lines.append(text)
                    blocks.append({
                        "text": text,
                        "bbox": {
                            "x_min": float(b[0]),
                            "y_min": float(b[1]),
                            "x_max": float(b[2]),
                            "y_max": float(b[3])
                        },
                        "is_heading": text.isupper() and len(text) < 60
                    })

            if blocks:
                page_layouts.append({
                    "page": page_idx + 1,
                    "text": "\n".join(page_lines),
                    "blocks": blocks,
                    "image_width": float(width) if width else 600.0,
                    "image_height": float(height) if height else 800.0
                })
        doc.close()
    except Exception:
        pass

    return page_layouts


def convert_pdf_to_images(pdf_path, dpi=150, max_pages=10):
    """
    Renders PDF pages into PIL Images using PyMuPDF (fitz) with fallback.
    DPI 150 gives crystal clear OCR with 4x faster rendering.
    """
    images = []

    # 1. Try PyMuPDF (fitz)
    try:
        import fitz
        doc = fitz.open(pdf_path)
        num_pages = min(len(doc), max_pages)
        for page_num in range(num_pages):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=dpi)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data)).convert("RGB")
            images.append(img)
        doc.close()
        if images:
            return images
    except Exception:
        pass

    # 2. Fallback to pdf2image
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=max_pages)
        if images:
            return images
    except Exception:
        pass

    if not images:
        raise RuntimeError("Failed to render PDF pages into images.")

    return images

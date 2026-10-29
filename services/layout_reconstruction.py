"""
Pixel-to-Text Document Reconstruction Engine.

Recreates uploaded documents as selectable text-only output using OCR
bounding-box coordinates (x, y, width, height) for line grouping, column
alignment, table preservation, and spacing — not AI prompting alone.

For 90%+ layout accuracy, always feed word_boxes or blocks with bbox data.
The DOCUMENT_RECONSTRUCTION_PROMPT below is for optional LLM post-processing;
the primary path is coordinate-based reconstruction via build_char_grid().
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

DOCUMENT_RECONSTRUCTION_PROMPT = """\
# PIXEL-TO-TEXT DOCUMENT RECONSTRUCTION

You are an AI Document Reconstruction Engine.

Your task is to recreate the uploaded document as TEXT ONLY.
The output must visually resemble the original document as closely as possible while remaining fully selectable text.

## PRIMARY GOAL

Convert: Document Image → OCR + Layout Analysis → Formatted Text

The formatted text should preserve: document structure, positioning, columns, tables,
alignment, margins, headers, footers, spacing, blank lines, and reading order.

## IMPORTANT

Do NOT summarize. Do NOT extract key fields only. Do NOT output JSON.
Do NOT output structured fields. Do NOT generate explanations.
Output ONLY the reconstructed document text.

## COLUMN PRESERVATION

Never merge multi-column lines into one line. Preserve left/right positioning.

## TABLE PRESERVATION

Preserve table layout. Do not flatten tables.

## SPACING PRESERVATION

Maintain indentation, margins, blank lines, alignment, table columns, and section gaps.
Generate spaces based on OCR coordinates. Never collapse all spaces.

## OCR LAYOUT RULE

Use OCR bounding boxes and coordinates. Use X positions for horizontal spacing.
Use Y positions for line grouping. Use document width to calculate relative spacing.

## NO INFORMATION LOSS

Every OCR word detected in the image must appear in the final formatted text.

## FINAL OUTPUT

Return ONLY the reconstructed text document.
"""

FMT_COLS = 120
PAGE_SEPARATOR = "=" * 24
MAX_BLANK_LINES = 4
NUMERIC_RE = re.compile(r"^[\d$€£₹.,%-]+$")


def _bbox_from_box(box: Any) -> Optional[Tuple[float, float, float, float]]:
    """Normalize polygon or {x,y,w,h} boxes to (x1, y1, x2, y2)."""
    if not box:
        return None

    try:
        if isinstance(box, dict):
            x1 = float(box.get("x_min", box.get("x", 0)))
            y1 = float(box.get("y_min", box.get("y", 0)))
            x2 = float(box.get("x_max", x1 + float(box.get("width", 0))))
            y2 = float(box.get("y_max", y1 + float(box.get("height", 0))))
            return x1, y1, x2, y2

        if isinstance(box, (list, tuple)) and len(box) >= 4:
            if isinstance(box[0], (list, tuple)):
                xs = [float(pt[0]) for pt in box if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                ys = [float(pt[1]) for pt in box if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                if xs and ys:
                    return min(xs), min(ys), max(xs), max(ys)
            x1, y1, w, h = float(box[0]), float(box[1]), float(box[2]), float(box[3])
            return x1, y1, x1 + w, y1 + h
    except (TypeError, ValueError):
        return None

    return None


def _item_from_bbox(text: str, bbox: Tuple[float, float, float, float], is_heading: bool = False) -> Dict[str, Any]:
    x1, y1, x2, y2 = bbox
    return {"text": text, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "is_heading": is_heading}


def parse_block_items(blocks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for block in blocks or []:
        text = str(block.get("text") or "").strip()
        bbox = _bbox_from_box(block.get("bbox"))
        if text and bbox:
            items.append(_item_from_bbox(text, bbox, bool(block.get("is_heading"))))
    return items


def parse_word_box_items(word_boxes: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in word_boxes or []:
        text = str(entry.get("text") or entry.get("word") or "").strip()
        bbox = _bbox_from_box(entry.get("box"))
        if text and bbox:
            items.append(_item_from_bbox(text, bbox))
    return items


def parse_bounding_box_items(
    bounding_boxes: Sequence[Any],
    raw_lines: Sequence[str],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    count = min(len(bounding_boxes or []), len(raw_lines or []))
    for i in range(count):
        text = str(raw_lines[i]).strip()
        bbox = _bbox_from_box(bounding_boxes[i])
        if text and bbox:
            items.append(_item_from_bbox(text, bbox))
    return items


def compute_avg_line_height(items: Sequence[Dict[str, Any]]) -> float:
    heights = [item["y2"] - item["y1"] for item in items if item["y2"] - item["y1"] > 2]
    if not heights:
        return 20.0
    heights.sort()
    return heights[len(heights) // 2]


def cluster_into_lines(items: Sequence[Dict[str, Any]], avg_h: float) -> List[List[Dict[str, Any]]]:
    groups: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    margin = max(avg_h * 0.45, 6.0)

    for item in sorted(items, key=lambda i: (i["y1"], i["x1"])):
        if not current:
            current = [item]
            continue

        g_top = min(i["y1"] for i in current)
        g_bottom = max(i["y2"] for i in current)
        i_center = (item["y1"] + item["y2"]) / 2.0

        if g_top - margin <= i_center <= g_bottom + margin:
            current.append(item)
        else:
            groups.append(current)
            current = [item]

    if current:
        groups.append(current)
    return groups


def _x_to_col(x: float, img_w: float) -> int:
    return max(0, round((x / max(img_w, 1.0)) * FMT_COLS))


def _is_numeric(text: str) -> bool:
    return bool(NUMERIC_RE.match(text.strip()))


def _is_right_aligned_item(item: Dict[str, Any], img_w: float) -> bool:
    text = item["text"].strip()
    if _is_numeric(text):
        return True
    if item["x1"] >= img_w * 0.55 and len(text) <= 20:
        return True
    return False


def _detect_column_anchors(items: Sequence[Dict[str, Any]], img_w: float) -> List[float]:
    """Cluster recurring X positions into column anchors for table alignment."""
    threshold = max(img_w * 0.025, 10.0)
    positions: List[float] = []

    for item in items:
        positions.append(item["x1"])
        if _is_right_aligned_item(item, img_w):
            positions.append(item["x2"])

    if not positions:
        return []

    positions.sort()
    anchors: List[float] = []
    for pos in positions:
        if not anchors or pos - anchors[-1] > threshold:
            anchors.append(pos)
        else:
            anchors[-1] = (anchors[-1] + pos) / 2.0
    return anchors


def _snap_x(x: float, anchors: Sequence[float], img_w: float) -> float:
    if not anchors:
        return x
    nearest = min(anchors, key=lambda a: abs(a - x))
    if abs(nearest - x) <= max(img_w * 0.035, 14.0):
        return nearest
    return x


def _is_centered_heading(line_items: Sequence[Dict[str, Any]], img_w: float) -> bool:
    if len(line_items) != 1:
        return False
    item = line_items[0]
    text = item["text"]
    if not text or len(text) > 60:
        return False
    center = (item["x1"] + item["x2"]) / 2.0
    return (
        text == text.upper()
        and any(c.isalpha() for c in text)
        and abs(center - img_w / 2.0) <= img_w * 0.12
    )


def _build_line_string(
    line_items: Sequence[Dict[str, Any]],
    img_w: float,
    anchors: Sequence[float],
) -> str:
    """Place items on a character grid using X for spacing, X2 for right-aligned values."""
    if not line_items:
        return ""

    buffer = [" "] * (FMT_COLS + 40)
    sorted_items = sorted(line_items, key=lambda i: i["x1"])

    for item in sorted_items:
        text = item["text"]
        if not text:
            continue

        if _is_centered_heading([item], img_w):
            center_col = _x_to_col((item["x1"] + item["x2"]) / 2.0, img_w)
            start_col = max(0, center_col - len(text) // 2)
        elif _is_right_aligned_item(item, img_w):
            anchor_x = _snap_x(item["x2"], anchors, img_w)
            start_col = max(0, _x_to_col(anchor_x, img_w) - len(text))
        else:
            anchor_x = _snap_x(item["x1"], anchors, img_w)
            start_col = _x_to_col(anchor_x, img_w)

        for offset, char in enumerate(text):
            pos = start_col + offset
            if pos >= len(buffer):
                buffer.extend([" "] * (pos - len(buffer) + 1))
            if buffer[pos] == " ":
                buffer[pos] = char

    return "".join(buffer).rstrip()


def build_char_grid(items: Sequence[Dict[str, Any]], img_w: float, img_h: float) -> str:
    """Reconstruct page text from coordinate-positioned OCR items."""
    if not items:
        return ""

    avg_h = compute_avg_line_height(items)
    line_groups = cluster_into_lines(items, avg_h)
    anchors = _detect_column_anchors(items, img_w)

    output_lines: List[str] = []
    prev_bottom = -1.0

    for line_items in line_groups:
        line_top = min(i["y1"] for i in line_items)
        if prev_bottom >= 0:
            gap = line_top - prev_bottom
            blanks = max(0, min(MAX_BLANK_LINES, round(gap / avg_h) - 1))
            output_lines.extend([""] * blanks)

        prev_bottom = max(i["y2"] for i in line_items)

        is_heading = (
            any(i.get("is_heading") for i in line_items)
            or _is_centered_heading(line_items, img_w)
        )
        if is_heading and output_lines and output_lines[-1] != "":
            output_lines.append("")

        output_lines.append(_build_line_string(line_items, img_w, anchors))

        if is_heading:
            output_lines.append("")

    while output_lines and output_lines[0] == "":
        output_lines.pop(0)
    while output_lines and output_lines[-1] == "":
        output_lines.pop()

    return "\n".join(output_lines)


def smart_text_reconstruct(raw_text: str) -> str:
    """Coordinate-free fallback — preserves structure but lower layout accuracy."""
    if not raw_text or not raw_text.strip():
        return ""

    # Detect if this is an invoice/receipt for special formatting
    is_invoice = _detect_invoice_document(raw_text)
    if is_invoice:
        return _format_invoice_text(raw_text)

    output: List[str] = []
    for line in raw_text.split("\n"):
        trimmed = line.strip()
        if not trimmed:
            if not output or output[-1] != "":
                output.append("")
            continue

        is_all_caps = (
            trimmed == trimmed.upper()
            and 2 < len(trimmed) < 60
            and any(c.isalpha() for c in trimmed)
        )
        is_key_value = bool(re.match(r"^[A-Za-z\s#\/]+:\s*.+$", trimmed))
        is_separator = bool(re.match(r"^[-=_*#]{3,}$", trimmed))
        cols = re.split(r"\s{2,}", trimmed)
        is_table_row = len(cols) >= 3 and bool(re.search(r"[\d$€£₹%]", trimmed))

        if is_separator:
            output.append(trimmed)
        elif is_table_row:
            col_width = max(8, FMT_COLS // len(cols))
            row = "".join(c.ljust(col_width) for c in cols)
            output.append(row.rstrip())
        elif is_all_caps and not is_key_value:
            if output and output[-1] != "":
                output.append("")
            output.append(trimmed)
            output.append("")
        else:
            output.append(trimmed)

    return "\n".join(output).strip()


def _detect_invoice_document(text: str) -> bool:
    """Detect if text is from an invoice or receipt."""
    invoice_keywords = ["invoice", "bill to", "ship to", "description", "qty", "quantity", 
                       "price", "total", "amount", "payment", "due date", "receipt", "subtotal"]
    text_lower = text.lower()
    keyword_count = sum(1 for kw in invoice_keywords if kw in text_lower)
    return keyword_count >= 2


def _format_invoice_text(raw_text: str) -> str:
    """Format invoice/receipt text with proper table structure and alignment."""
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    if not lines:
        return ""

    formatted = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Detect and format table headers
        if any(kw in line.lower() for kw in ["description", "item", "qty", "quantity", "price", "total", "amount"]):
            formatted.append("\n" + line.upper())
            i += 1
            # Collect table rows
            table_rows = []
            while i < len(lines) and _is_invoice_table_row(lines[i]):
                table_rows.append(lines[i])
                i += 1
            # Format table rows with alignment
            if table_rows:
                formatted.extend(_align_invoice_table([line.upper()] + table_rows))
            continue
        
        # Format totals section
        if any(kw in line.lower() for kw in ["total", "subtotal", "tax", "due", "balance"]):
            formatted.append("\n" + line)
            i += 1
            continue
        
        # Format payment/billing info
        if any(kw in line.lower() for kw in ["bill to", "ship to", "invoice", "date", "payment", "bank", "account"]):
            formatted.append(line)
            i += 1
            continue
        
        # Regular content
        formatted.append(line)
        i += 1
    
    return "\n".join(formatted).strip()


def _parse_numeric_token(tok: str) -> Optional[str]:
    """Return a cleaned numeric token if tok looks like a currency/number, otherwise None."""
    if not tok or not any(ch.isdigit() for ch in tok):
        return None
    # Remove surrounding spaces
    t = tok.strip()
    # Accept currency symbols and commas
    m = re.match(r"^([€£₹$]?\s*[\d,]+(?:\.\d+)?)$", t)
    if m:
        return m.group(1)
    # Also accept plain numbers like 2000 or 3.0
    m2 = re.match(r"^[\d,]+(?:\.\d+)?$", t)
    if m2:
        return m2.group(0)
    return None


def _split_invoice_row(line: str, max_trailing_numbers: int = 3) -> List[str]:
    """Split a line into [description, qty, unit_price, total_price] when possible.

    Strategy: scan tokens from the right, collecting up to `max_trailing_numbers` numeric-like tokens
    (currency-aware). The remaining left side is treated as the description.
    """
    tokens = line.strip().split()
    if not tokens:
        return [line]

    trailing = []
    i = len(tokens) - 1
    while i >= 0 and len(trailing) < max_trailing_numbers:
        candidate = tokens[i]
        num = _parse_numeric_token(candidate)
        if num is not None:
            trailing.insert(0, candidate)
            i -= 1
            continue
        # If candidate ends with a numeric characters after stripping punctuation, try to strip punctuation
        stripped = candidate.rstrip(',')
        num2 = _parse_numeric_token(stripped)
        if num2 is not None:
            trailing.insert(0, stripped)
            i -= 1
            continue
        break

    desc_tokens = tokens[: i + 1]
    description = " ".join(desc_tokens).strip() if desc_tokens else ""

    # Build result: description + trailing numbers (left padded to length 3)
    result = [description] if description else [""]
    # Pad left so that we always return 4 columns (description, qty, unit, total)
    # Place the trailing numbers at the end
    padded = [""] * (3 - len(trailing)) + trailing
    result.extend(padded)
    return result


def _is_invoice_table_row(line: str) -> bool:
    """Check if a line appears to be an invoice table row.

    More robust detection: a row is considered invoice-like if it contains at least one numeric token
    and either contains currency symbols or multiple numeric tokens indicating qty/unit/amount.
    """
    if not line or not any(c.isdigit() for c in line):
        return False
    num_tokens = 0
    has_currency = any(sym in line for sym in ["$", "€", "£", "₹"]) 
    for tok in line.split():
        if _parse_numeric_token(tok) is not None:
            num_tokens += 1
    return has_currency or num_tokens >= 1


def _align_invoice_table(rows: List[str]) -> List[str]:
    """Align invoice table rows for better readability.

    This version attempts to split each row into description + up to 3 numeric columns (qty, unit, total)
    using _split_invoice_row and then aligns columns, right-aligning numeric columns.
    """
    if not rows:
        return []

    # Use the first row as header if it seems non-numeric
    header = rows[0]
    body = rows[1:] if len(rows) > 1 else rows

    parsed_rows = []
    # Include header as a row of strings (will be padded)
    parsed_rows.append(header.split())

    for row in body:
        parsed = _split_invoice_row(row, max_trailing_numbers=3)
        parsed_rows.append(parsed)

    # Determine number of columns
    num_cols = max(len(r) for r in parsed_rows)
    # Normalize rows to lists of strings
    norm_rows = [ [str(c) for c in r] + [""] * (num_cols - len(r)) for r in parsed_rows ]

    # Compute column widths
    col_widths = [0] * num_cols
    for r in norm_rows:
        for i, cell in enumerate(r):
            col_widths[i] = max(col_widths[i], len(cell))

    # Format rows: right-align numeric columns (last 3), left-align first (description/header)
    aligned = []
    for r in norm_rows:
        parts = []
        for i, cell in enumerate(r):
            # Decide alignment: last 3 columns numeric-right, others left
            if i >= max(1, num_cols - 3):
                parts.append(cell.rjust(col_widths[i]))
            else:
                parts.append(cell.ljust(col_widths[i]))
        aligned.append("  ".join(parts).rstrip())

    return aligned



def _collect_page_items(page_layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prefer finest-grained coordinate source: word_boxes > blocks > boxes."""
    page_text = page_layout.get("text") or ""
    raw_lines = [line.strip() for line in page_text.split("\n") if line.strip()]

    word_boxes = page_layout.get("word_boxes") or []
    blocks = page_layout.get("blocks") or []
    boxes = page_layout.get("boxes") or []

    if word_boxes:
        return parse_word_box_items(word_boxes)
    if blocks:
        return parse_block_items(blocks)
    if boxes and raw_lines:
        return parse_bounding_box_items(boxes, raw_lines)
    return []


def _dedupe_repeated_tokens(lines: Sequence[str]) -> List[str]:
    """Compress consecutive duplicate lines while preserving single blank lines.

    - Keeps repeated but non-adjacent tokens.
    - Collapses runs of blank lines into a single blank line (preserve spacing).
    """
    result: List[str] = []
    prev = None
    for line in lines:
        # Preserve original blank lines (represented as empty string after strip)
        normalized = re.sub(r"\s+", " ", line.strip())
        if normalized == "":
            # keep a single blank line between content blocks
            if prev != "":
                result.append("")
                prev = ""
            continue
        if prev is not None and normalized.lower() == (prev.lower() if prev != "" else prev):
            # skip consecutive duplicate non-empty lines
            continue
        result.append(normalized)
        prev = normalized
    return result


def _format_receipt_like_layout(page_layout: Dict[str, Any], raw_text: str = "") -> str:
    """Build a receipt-like text layout from OCR word positions instead of a flat paragraph dump.

    Improvements over prior version:
    - Preserve blank lines from the char-grid reconstruction.
    - Avoid duplicating the detected title line.
    - Dynamically size the box with a higher upper limit to avoid truncation.
    - Right-align detected amounts/currency tokens inside the box for improved readability.
    """
    page_text = (page_layout or {}).get("text") or raw_text or ""
    items = _collect_page_items(page_layout)
    if not items and page_text.strip():
        items = [
            _item_from_bbox(line, (0.0, 0.0, 10.0, 10.0))
            for line in [ln for ln in page_text.splitlines()]
        ]

    if not items:
        return smart_text_reconstruct(page_text)

    # Reconstruct a character grid preserving X/Y positions
    img_w = float(page_layout.get("image_width") or 1000)
    img_h = float(page_layout.get("image_height") or 1000)
    grid_text = build_char_grid(items, img_w, img_h)
    # Preserve blank lines (do not filter them out)
    grid_lines = [ln.rstrip() for ln in grid_text.splitlines()]

    # If the grid did not produce meaningful lines, fallback to smart_text_reconstruct
    if not any(ln.strip() for ln in grid_lines):
        return smart_text_reconstruct(page_text)

    # Deduplicate only consecutive repeats and compress blank runs
    grid_lines = _dedupe_repeated_tokens(grid_lines)

    # Determine box inner width (clamp to reasonable range). Allow wider boxes to avoid clipping.
    max_len = max((len(ln) for ln in grid_lines), default=36)
    inner_width = min(max(36, max_len), 240)

    # Build boxed output
    top = "┌" + "─" * (inner_width + 2) + "┐"
    bottom = "└" + "─" * (inner_width + 2) + "┘"
    output: List[str] = [top]

    # Try to find an explicit title (RECEIPT/INVOICE) to center
    title_idx = None
    for i, ln in enumerate(grid_lines[:6]):
        if re.search(r"\b(receipt|invoice)\b", ln, re.I) or (ln.strip() == ln.strip().upper() and len(ln.strip()) <= 60 and any(c.isalpha() for c in ln.strip())):
            title_idx = i
            break

    added_title = False
    if title_idx is not None:
        title_line = grid_lines[title_idx].strip()
        output.append("│ " + title_line.center(inner_width) + " │")
        output.append("│ " + " " * inner_width + " │")
        added_title = True

    # Add every line preserving left alignment but padded to inner width
    # If the line is the detected title and we've already added it, skip to avoid duplication.
    amount_re = re.compile(r"([€£₹$]\s*[\d,]+(?:\.\d{1,2})?|\d[\d,]*\.\d{1,2})\s*$")
    for idx, ln in enumerate(grid_lines):
        if added_title and idx == title_idx:
            continue
        display = ln.rstrip()
        if display == "":
            # blank line — preserve as an empty row
            output.append("│ " + " " * inner_width + " │")
            continue

        # Try to detect a trailing currency/amount token to right-align it inside the box
        m = amount_re.search(display)
        if m:
            amount = m.group(0).strip()
            left = display[: m.start()].rstrip()
            # Ensure the amount fits; if left is too long, truncate intelligently
            available = inner_width - len(amount)
            if available <= 0:
                # Amount itself longer than inner width — truncate amount
                amt_disp = amount[-inner_width:]
                output.append("│ " + f"{amt_disp:>{inner_width}}" + " │")
            else:
                left_disp = (left[:available]).ljust(available)
                output.append("│ " + left_disp + amount.rjust(len(amount)) + " │")
            continue

        # Default left-aligned row, truncate if too long
        if len(display) > inner_width:
            display = display[:inner_width]
        output.append("│ " + f"{display:<{inner_width}}" + " │")

    output.append(bottom)
    return "\n".join(output)


def reconstruct_page(page_layout: Dict[str, Any]) -> str:
    """Reconstruct a single page using OCR bounding-box coordinates."""
    img_w = float(page_layout.get("image_width") or 1000)
    img_h = float(page_layout.get("image_height") or 1000)
    page_text = page_layout.get("text") or ""

    if page_text.strip() and re.search(r"\b(receipt|invoice|total|cash|change|qty|amount)\b", page_text, re.I):
        page_layout = dict(page_layout)
        page_layout["text"] = page_text
        return _format_receipt_like_layout(page_layout, page_text)

    items = _collect_page_items(page_layout)
    if items:
        return build_char_grid(items, img_w, img_h)
    if page_text.strip():
        return smart_text_reconstruct(page_text)
    return ""


def reconstruct_document(
    page_layouts: Optional[Sequence[Dict[str, Any]]] = None,
    raw_text: str = "",
    bounding_boxes: Optional[Sequence[Any]] = None,
) -> str:
    """
    Reconstruct full document as text-only formatted output.

    Returns ONLY the reconstructed document text — no JSON, no summaries.
    """
    pages: List[str] = []
    page_layouts = page_layouts or []

    for page in page_layouts:
        page_output = reconstruct_page(page)
        if page_output:
            pages.append(page_output)

    if not pages:
        if bounding_boxes and raw_text.strip():
            raw_lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
            items = parse_bounding_box_items(bounding_boxes, raw_lines)
            if items:
                max_x = max(i["x2"] for i in items)
                max_y = max(i["y2"] for i in items)
                return build_char_grid(items, max_x, max_y)
        if raw_text.strip():
            return smart_text_reconstruct(raw_text)
        return ""

    if len(pages) == 1:
        return pages[0]

    formatted_pages = []
    for idx, content in enumerate(pages, start=1):
        formatted_pages.append(f"{PAGE_SEPARATOR}\nPAGE {idx}\n\n{content}")
    return "\n\n".join(formatted_pages)


# =====================================================================
# HTML & Visual Layout Reconstruction Engine
# Recreates documents matching original layout:
# - White paper background (.formatted-document-sheet)
# - Left/right alignment preservation
# - Semantic HTML <table> with aligned columns (no ASCII / | | |)
# - Font hierarchy (title, labels, normal text, bold emphasis)
# =====================================================================

AMOUNT_RE = re.compile(r"[$€£₹]\s*[\d,]+(?:\.\d{1,2})?|[\d,]+\.\d{2}")

KNOWN_MULTIWORD_HEADERS = [
    "service description", "item description", "product description", "item name",
    "unit price", "unit cost", "unit rate", "total price", "total amount",
    "line total", "net amount", "gross amount", "tax rate", "tax amount",
    "hsn code", "sac code", "serial no", "part number", "patient name",
    "receipt date", "invoice date", "due date", "order date"
]


def clean_ocr_token(text: str) -> str:
    """Clean OCR noise and strip trailing/leading pipes (|)."""
    if not text:
        return ""
    t = str(text).strip()
    t = re.sub(r"^[\s\|\:\-]+", "", t)
    t = re.sub(r"[\s\|\:\-]+$", "", t)
    t = re.sub(r"\|\s*\|+", "|", t)
    t = re.sub(r"[ \t]+", " ", t).strip()
    return t


def is_key_value_line(line: str) -> Optional[Tuple[str, str]]:
    """Detect 'Key : Value' line and return (key, value) or None."""
    cleaned = line.strip().rstrip("|").strip()
    m = re.match(r"^([A-Za-z0-9\s#/\(\)\.\-_]{2,45})\s*:\s*(.+)$", cleaned)
    if m:
        k = m.group(1).strip()
        v = m.group(2).strip().rstrip("|").strip()
        if len(k) >= 2 and len(v) >= 1:
            return (k, v)
    return None


def is_total_line(line: str) -> bool:
    """Check if line is a subtotal/total/balance due line."""
    cleaned = line.lower()
    return any(kw in cleaned for kw in [
        "total amount due", "total due", "total amount", "grand total",
        "subtotal", "tax total", "balance due", "amount payable", "net total", "total:"
    ])


def parse_table_headers(header_line: str) -> List[str]:
    """Parse table headers, preserving multi-word columns like 'Service Description' and 'Unit Price'."""
    cleaned = header_line.strip().rstrip("|").strip()
    if "|" in cleaned:
        cols = [c.strip() for c in cleaned.split("|") if c.strip()]
        if len(cols) >= 2:
            return cols

    spaced = [p.strip() for p in re.split(r"\t+|\s{2,}", cleaned) if p.strip()]
    if len(spaced) >= 3:
        return spaced

    # Recognize known multi-word headers
    temp = cleaned
    placeholders = {}
    for idx, phrase in enumerate(KNOWN_MULTIWORD_HEADERS):
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        match = pattern.search(temp)
        if match:
            ph = f"__MULTI_{idx}__"
            placeholders[ph] = match.group(0)
            temp = pattern.sub(ph, temp)

    tokens = temp.split()
    cols = []
    for tok in tokens:
        if tok in placeholders:
            cols.append(placeholders[tok])
        else:
            cols.append(tok)

    return cols


def parse_table_row_tokens(row_text: str) -> List[str]:
    """Split line into table cells with description on left and numbers on right."""
    cleaned = row_text.strip().rstrip("|").strip()
    if "|" in cleaned:
        cells = [c.strip() for c in cleaned.split("|") if c.strip()]
        if len(cells) >= 2:
            return cells

    spaced_parts = [p.strip() for p in re.split(r"\t+|\s{2,}", cleaned) if p.strip()]
    if len(spaced_parts) >= 2:
        return spaced_parts

    tokens = cleaned.split()
    if len(tokens) < 2:
        return [cleaned]

    numeric_indices = []
    for idx in range(len(tokens) - 1, -1, -1):
        tok = tokens[idx].rstrip("|").strip()
        if NUMERIC_RE.match(tok) or AMOUNT_RE.match(tok):
            numeric_indices.insert(0, idx)
        else:
            break

    if numeric_indices:
        split_point = numeric_indices[0]
        desc = " ".join(tokens[:split_point]).strip()
        nums = [tokens[i].rstrip("|").strip() for i in numeric_indices]
        if desc:
            return [desc] + nums
        return nums

    return tokens


def is_table_header_line(line: str) -> bool:
    """Check if line contains multiple table header columns."""
    cleaned = line.lower().strip().rstrip("|").strip()
    if ":" in cleaned:
        return False
    headers = ["description", "service", "item", "qty", "quantity", "price", "unit price", "rate", "total", "amount"]
    matches = sum(1 for h in headers if h in cleaned)
    return matches >= 2


def reconstruct_page_html(
    page_layout: Optional[Dict[str, Any]] = None,
    raw_text: str = "",
    structured_data: Optional[Dict[str, Any]] = None,
    tables: Optional[List[Any]] = None,
    doc_type: str = "Document",
    page_number: int = 1,
) -> str:
    """
    Reconstruct a single page as high-fidelity visual HTML.
    Preserves:
    - Pure white paper background (.formatted-document-sheet)
    - Original header hierarchy and title
    - Left/right spatial alignment of metadata
    - Real semantic HTML <table> with proper column alignment
    - Prominent totals card
    - Clean footer without | | | separators
    """
    page_layout = page_layout or {}
    page_text = page_layout.get("text") or raw_text or ""
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]

    # Extract header / title
    title = doc_type or "Document"
    brand_header = ""
    consumed_indices = set()

    for idx, ln in enumerate(lines[:6]):
        clean_ln = ln.rstrip("|").strip()
        if ":" in clean_ln:
            continue
        if re.search(r"\b(receipt|invoice|bill|statement|resume|report|prescription|patient receipt)\b", clean_ln, re.I):
            title = clean_ln
            consumed_indices.add(idx)
            if idx > 0 and not brand_header and len(lines[0]) < 50 and ":" not in lines[0]:
                brand_header = lines[0].rstrip("|").strip()
                consumed_indices.add(0)
            break
        elif clean_ln.isupper() and len(clean_ln) < 40 and not any(c.isdigit() for c in clean_ln[:3]):
            title = clean_ln
            consumed_indices.add(idx)
            break

    # If title looks generic but doc_type is specific, prefer specific
    if (not title or title.lower() in ("document", "general document")) and doc_type and doc_type.lower() not in ("document", "general document"):
        title = doc_type

    # Categorize remaining lines
    meta_pairs: List[Tuple[str, str]] = []
    table_rows: List[List[str]] = []
    table_headers: List[str] = []
    total_lines: List[str] = []
    footer_lines: List[str] = []
    in_table = False

    for idx, ln in enumerate(lines):
        if idx in consumed_indices:
            continue
        clean_ln = clean_ocr_token(ln)
        if not clean_ln:
            continue

        # Check total lines
        if is_total_line(clean_ln):
            in_table = False
            total_lines.append(clean_ln)
            continue

        # Check footer / contact info lines
        if any(kw in clean_ln.lower() for kw in ["thank you", "terms", "condition", "@", "www.", ".com", ".net", "inquire@"]):
            if idx > len(lines) * 0.5:
                in_table = False
                footer_lines.append(clean_ln)
                continue

        # Check table header
        if is_table_header_line(clean_ln):
            in_table = True
            table_headers = parse_table_headers(clean_ln)
            continue

        # If inside table
        if in_table:
            row_cells = parse_table_row_tokens(clean_ln)
            if len(row_cells) >= 2 or any(NUMERIC_RE.match(c) or AMOUNT_RE.match(c) for c in row_cells):
                table_rows.append(row_cells)
                continue
            else:
                in_table = False

        # Check key-value line
        kv = is_key_value_line(clean_ln)
        if kv:
            meta_pairs.append(kv)
            continue

        # Fallback text
        footer_lines.append(clean_ln)

    # Use structured tables if provided and no OCR table rows detected
    if not table_rows and tables:
        for t in tables:
            if isinstance(t, dict):
                if t.get("headers"):
                    table_headers = [str(h) for h in t["headers"]]
                if t.get("rows"):
                    for r in t["rows"]:
                        if isinstance(r, (list, tuple)):
                            table_rows.append([str(c) for c in r])
                        elif isinstance(r, dict):
                            headers = table_headers or list(r.keys())
                            table_rows.append([str(r.get(h, "")) for h in headers])

    # Assemble HTML
    parts = [f'<div class="formatted-document-sheet" data-theme-surface="paper" data-page="{page_number}">']

    # 1. Header
    parts.append('  <header class="doc-header">')
    if brand_header:
        parts.append(f'    <div class="doc-brand">{html.escape(brand_header)}</div>')
    parts.append(f'    <h1 class="doc-title">{html.escape(title)}</h1>')
    parts.append('  </header>')

    # 2. Metadata Section (Left & Right Split)
    if meta_pairs:
        left_pairs = []
        right_pairs = []
        for k, v in meta_pairs:
            k_low = k.lower()
            if any(term in k_low for term in ["date", "time", "no", "number", "invoice", "receipt", "id"]):
                right_pairs.append((k, v))
            else:
                left_pairs.append((k, v))

        if not right_pairs and len(left_pairs) >= 2:
            mid = (len(left_pairs) + 1) // 2
            right_pairs = left_pairs[mid:]
            left_pairs = left_pairs[:mid]

        parts.append('  <section class="doc-meta-section">')
        parts.append('    <div class="doc-row doc-row-split">')

        parts.append('      <div class="doc-col doc-col-left">')
        for k, v in left_pairs:
            parts.append(f'        <div class="doc-kv"><span class="doc-kv-label">{html.escape(k)}:</span> <span class="doc-kv-val">{html.escape(v)}</span></div>')
        parts.append('      </div>')

        parts.append('      <div class="doc-col doc-col-right">')
        for k, v in right_pairs:
            parts.append(f'        <div class="doc-kv"><span class="doc-kv-label">{html.escape(k)}:</span> <span class="doc-kv-val">{html.escape(v)}</span></div>')
        parts.append('      </div>')

        parts.append('    </div>')
        parts.append('  </section>')

    # 3. Table Section
    if table_rows:
        parts.append('  <section class="doc-table-section">')
        parts.append('    <div class="doc-table-wrap">')
        parts.append('      <table class="doc-table">')

        if table_headers:
            parts.append('        <thead>')
            parts.append('          <tr>')
            for idx, h in enumerate(table_headers):
                align_cls = "col-numeric" if idx > 0 and any(kw in h.lower() for kw in ["qty", "quantity", "price", "rate", "total", "amount"]) else "col-desc"
                parts.append(f'            <th class="{align_cls}">{html.escape(h)}</th>')
            parts.append('          </tr>')
            parts.append('        </thead>')

        parts.append('        <tbody>')
        for row in table_rows:
            parts.append('          <tr>')
            for idx, cell in enumerate(row):
                cell_str = str(cell).strip()
                align_cls = "col-numeric" if idx > 0 and (NUMERIC_RE.match(cell_str) or AMOUNT_RE.match(cell_str)) else "col-desc"
                parts.append(f'            <td class="{align_cls}">{html.escape(cell_str)}</td>')
            parts.append('          </tr>')
        parts.append('        </tbody>')
        parts.append('      </table>')
        parts.append('    </div>')
        parts.append('  </section>')

    # 4. Totals Section
    if total_lines:
        parts.append('  <section class="doc-totals-section">')
        parts.append('    <div class="doc-totals-box">')
        for tl in total_lines:
            kv = is_key_value_line(tl)
            if kv:
                k, v = kv
                parts.append(f'      <div class="doc-total-row doc-total-highlight"><span class="doc-total-label">{html.escape(k)}:</span> <span class="doc-total-val">{html.escape(v)}</span></div>')
            else:
                parts.append(f'      <div class="doc-total-row doc-total-highlight"><span class="doc-total-val">{html.escape(tl)}</span></div>')
        parts.append('    </div>')
        parts.append('  </section>')

    # 5. Footer Section
    if footer_lines:
        parts.append('  <footer class="doc-footer">')
        for fl in footer_lines:
            if "|" in fl:
                items = [clean_ocr_token(c) for c in fl.split("|") if clean_ocr_token(c)]
                if items:
                    joined = ' <span class="doc-dot">&bull;</span> '.join(f'<span>{html.escape(it)}</span>' for it in items)
                    parts.append(f'    <div class="doc-footer-contact">{joined}</div>')
                    continue
            parts.append(f'    <p class="doc-footer-text">{html.escape(fl)}</p>')
        parts.append('  </footer>')

    parts.append('</div>')
    return "\n".join(parts)


def reconstruct_document_html(
    page_layouts: Optional[Sequence[Dict[str, Any]]] = None,
    raw_text: str = "",
    bounding_boxes: Optional[Sequence[Any]] = None,
    structured_data: Optional[Dict[str, Any]] = None,
    tables: Optional[List[Any]] = None,
    doc_type: str = "Document",
) -> str:
    """
    Reconstruct full document as layout-aware HTML for Formatted View.
    Supports multi-page documents and coordinate-based or text-based inputs.
    """
    page_layouts = page_layouts or []
    if not page_layouts:
        return reconstruct_page_html(
            raw_text=raw_text,
            structured_data=structured_data,
            tables=tables,
            doc_type=doc_type,
            page_number=1,
        )

    html_pages = []
    for idx, page in enumerate(page_layouts, start=1):
        p_html = reconstruct_page_html(
            page_layout=page,
            raw_text=raw_text if idx == 1 else "",
            structured_data=structured_data if idx == 1 else None,
            tables=tables if idx == 1 else None,
            doc_type=doc_type,
            page_number=idx,
        )
        if p_html:
            html_pages.append(p_html)

    return "\n".join(html_pages)


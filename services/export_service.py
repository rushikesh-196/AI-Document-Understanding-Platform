"""
Data Export Service (JSON, CSV, DOCX, PDF)
"""

import json
import io
import re
import pandas as pd
from docx import Document
from docx.shared import Pt, Inches, RGBColor

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage, KeepTogether
    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover
    REPORTLAB_AVAILABLE = False

def _safe_export_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
        return "" if text in {"[object Object]", "[Object object]", "null", "None", "undefined"} else text
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = []
        for item in value:
            text = _safe_export_text(item)
            if text:
                parts.append(text)
        return " | ".join(parts)
    if isinstance(value, dict):
        parts = []
        for key, val in value.items():
            text = _safe_export_text(val)
            if text:
                parts.append(f"{key}: {text}")
        return "\n".join(parts)
    return str(value).strip()


def build_clean_structured_json(data):
    """Build clean, machine-readable domain JSON without UI icons or metadata wrappers."""
    if not isinstance(data, dict):
        return {}

    doc_type = data.get("document_type") or "General Document"
    conf = data.get("confidence_score") or data.get("confidence") or 0.95
    if isinstance(conf, str):
        try:
            c_val = float(conf.rstrip('%'))
            conf_num = round(c_val / 100.0, 2) if c_val > 1.0 else round(c_val, 2)
        except Exception:
            conf_num = 0.95
    elif isinstance(conf, (int, float)):
        conf_num = round(conf / 100.0, 2) if conf > 1.0 else round(conf, 2)
    else:
        conf_num = 0.95

    flat_data = {}
    sd = data.get("structured_data")
    if isinstance(sd, dict):
        for k, v in sd.items():
            if v and str(v).strip():
                flat_data[k] = str(v).strip()

    ef = data.get("extracted_fields")
    if isinstance(ef, list):
        for item in ef:
            if isinstance(item, dict):
                k = item.get("field_key") or item.get("key") or item.get("field_name")
                v = item.get("value")
                if k and v and str(v).strip():
                    k_clean = str(k).lower().replace(" ", "_")
                    if k_clean not in flat_data:
                        flat_data[k_clean] = str(v).strip()
    elif isinstance(ef, dict):
        for k, v in ef.items():
            if v and str(v).strip():
                flat_data[k] = str(v).strip()

    patient = {}
    vendor = {}
    customer = {}
    receipt_meta = {}
    other_fields = {}

    for k, v in flat_data.items():
        k_lower = k.lower()
        if any(p in k_lower for p in ["patient_name", "patient_email", "patient_dob", "patient"]):
            key_name = k_lower.replace("patient_", "").replace("patient", "name")
            patient[key_name] = v
        elif any(p in k_lower for p in ["vendor_name", "merchant", "store_name", "clinic", "hospital"]):
            key_name = k_lower.replace("vendor_", "").replace("merchant_", "")
            vendor[key_name] = v
        elif any(p in k_lower for p in ["customer_name", "client_name", "customer", "client"]):
            key_name = k_lower.replace("customer_", "").replace("client_", "")
            customer[key_name] = v
        elif any(p in k_lower for p in ["date", "receipt_number", "invoice_number", "payment_method", "transaction_reference", "po_number"]):
            if "total" not in k_lower and "amount" not in k_lower:
                key_name = k_lower.replace("receipt_", "").replace("invoice_", "")
                receipt_meta[key_name] = v
            else:
                other_fields[k_lower] = v
        else:
            other_fields[k_lower] = v

    items = []
    raw_tables = data.get("tables") or []
    for t in raw_tables:
        if isinstance(t, dict):
            headers = [str(h).lower().strip() for h in t.get("headers", [])]
            rows = t.get("rows", [])
            for row in rows:
                if isinstance(row, list) and len(row) >= 2:
                    item_obj = {}
                    for idx, val in enumerate(row):
                        header_name = headers[idx] if idx < len(headers) else f"col_{idx+1}"
                        val_str = str(val).strip()
                        if any(d in header_name for d in ["desc", "item", "service", "particular"]):
                            item_obj["description"] = val_str
                        elif any(q in header_name for q in ["qty", "quantity"]):
                            try: item_obj["quantity"] = int(float(val_str))
                            except: item_obj["quantity"] = val_str
                        elif any(p in header_name for p in ["price", "rate", "unit"]):
                            try: item_obj["unit_price"] = float(re.sub(r'[^\d.]', '', val_str))
                            except: item_obj["unit_price"] = val_str
                        elif any(tot in header_name for tot in ["total", "amount"]):
                            try: item_obj["total"] = float(re.sub(r'[^\d.]', '', val_str))
                            except: item_obj["total"] = val_str
                        else:
                            item_obj[header_name.replace(" ", "_")] = val_str
                    if item_obj:
                        items.append(item_obj)

    clean_payload = {
        "document": {
            "type": doc_type,
            "confidence": conf_num
        }
    }

    if patient:
        clean_payload["patient"] = patient
    if vendor:
        clean_payload["vendor"] = vendor
    if customer:
        clean_payload["customer"] = customer

    if "receipt" in doc_type.lower():
        clean_payload["receipt"] = receipt_meta if receipt_meta else other_fields
    elif "invoice" in doc_type.lower():
        clean_payload["invoice"] = receipt_meta if receipt_meta else other_fields
    elif receipt_meta:
        clean_payload["details"] = receipt_meta

    if items:
        clean_payload["items"] = items

    total_val = other_fields.get("total_amount") or other_fields.get("total") or flat_data.get("total_amount") or flat_data.get("amount")
    if total_val is not None:
        try:
            clean_payload["total_amount"] = float(re.sub(r'[^\d.]', '', str(total_val)))
        except Exception:
            clean_payload["total_amount"] = total_val
    elif other_fields:
        for ok, ov in other_fields.items():
            if ok not in clean_payload.get("receipt", {}) and ok not in clean_payload.get("invoice", {}):
                clean_payload[ok] = ov

    return clean_payload


def export_to_json(data):
    """Export the clean domain structured JSON output without UI metadata wrappers."""
    clean_payload = build_clean_structured_json(data)
    return json.dumps(clean_payload, indent=2, ensure_ascii=False)


def _get_image_metadata(job_data, upload_folder='uploads'):
    """
    Extracts image and file specifications: resolution, dimensions, color mode, format, file size.
    Returns (meta_dict, image_file_path_or_None).
    """
    import os
    from PIL import Image as PILImage

    img_info = {
        "format": "Unknown",
        "dimensions": "N/A",
        "color_mode": "N/A",
        "file_size": job_data.get("file_size") or "N/A",
        "dpi": "N/A",
        "has_image": False
    }

    # Find the file on disk
    file_path = None
    sname = job_data.get("saved_file_name")
    if sname:
        p = os.path.join(upload_folder, sname)
        if os.path.exists(p):
            file_path = p

    if not file_path:
        jid = job_data.get("job_id") or job_data.get("id")
        if jid and os.path.exists(upload_folder):
            for fn in os.listdir(upload_folder):
                if fn.startswith(str(jid)):
                    file_path = os.path.join(upload_folder, fn)
                    break

    if not file_path:
        fname = job_data.get("filename")
        if fname:
            p = os.path.join(upload_folder, fname)
            if os.path.exists(p):
                file_path = p

    if not file_path or not os.path.exists(file_path):
        fname = job_data.get("filename", "")
        ext = fname.rsplit(".", 1)[-1].upper() if "." in fname else "Document"
        img_info["format"] = ext
        return img_info, None

    # Calculate actual file size if missing
    try:
        size_bytes = os.path.getsize(file_path)
        if size_bytes < 1024:
            img_info["file_size"] = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            img_info["file_size"] = f"{round(size_bytes / 1024.0, 1)} KB"
        else:
            img_info["file_size"] = f"{round(size_bytes / (1024.0 * 1024.0), 2)} MB"
    except Exception:
        pass

    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    if ext == "pdf":
        img_info["format"] = "PDF Document"
        try:
            import fitz
            doc = fitz.open(file_path)
            img_info["dimensions"] = f"{len(doc)} Page(s)"
            doc.close()
        except Exception:
            img_info["dimensions"] = "PDF Document"
        return img_info, None

    # Read image using PIL
    try:
        with PILImage.open(file_path) as im:
            w, h = im.size
            img_info["dimensions"] = f"{w} x {h} px"
            img_info["format"] = (im.format or ext.upper() or "IMAGE").upper()
            img_info["color_mode"] = im.mode or "RGB"
            img_info["has_image"] = True
            dpi = im.info.get("dpi")
            if dpi and isinstance(dpi, (tuple, list)) and len(dpi) >= 2:
                img_info["dpi"] = f"{int(dpi[0])} x {int(dpi[1])} DPI"
    except Exception:
        img_info["format"] = ext.upper() or "IMAGE"

    return img_info, file_path


def export_to_csv(data):
    """
    Generates a properly structured CSV containing all relevant extracted information
    from the uploaded document/image, including fields, values, confidence scores,
    document details, tables, and detected data.
    """
    # Backward compatibility for flat list of dicts from old callers/tests
    if isinstance(data, list):
        if not data:
            return "Section,Field_Name,Field_Value,Confidence_Score,Details,Document_ID,Filename,Document_Type\n"
        df = pd.DataFrame(data)
        return df.to_csv(index=False)

    if not isinstance(data, dict):
        return "Section,Field_Name,Field_Value,Confidence_Score,Details,Document_ID,Filename,Document_Type\n"

    # If it's a raw dictionary without job indicators, fallback to simple key-value DataFrame
    job_indicators = ["filename", "job_id", "id", "document_type", "extracted_fields", "structured_data", "summary", "tables"]
    if not any(k in data for k in job_indicators):
        df = pd.DataFrame([data])
        return df.to_csv(index=False)

    job_data = data
    doc_id = str(job_data.get("job_id") or job_data.get("id") or "N/A")
    filename = str(job_data.get("filename") or "document")
    doc_type = str(job_data.get("document_type") or "General Document")
    overall_conf = _format_confidence_str(job_data)
    engine = str(job_data.get("engine") or "PaddleOCR / WinOCR")
    proc_time = str(job_data.get("processing_time") or "N/A")
    timestamp = str(job_data.get("timestamp") or job_data.get("upload_time") or "N/A")
    language = str(job_data.get("detected_language") or "English").title()

    img_info, _ = _get_image_metadata(job_data)

    records = []

    def add_row(section, name, value, conf=overall_conf, details=""):
        val_str = str(value).strip() if value is not None else ""
        if not val_str or val_str in ["[object Object]", "None", "null"]:
            return
        records.append({
            "Section": section,
            "Field_Name": str(name).strip(),
            "Field_Value": val_str,
            "Confidence_Score": str(conf).strip() if conf else overall_conf,
            "Details": str(details).strip(),
            "Document_ID": doc_id,
            "Filename": filename,
            "Document_Type": doc_type
        })

    # 1. Document Overview & Metadata
    add_row("Document Details", "Filename", filename, "100%", "Source Uploaded File")
    add_row("Document Details", "Document Classification", doc_type, overall_conf, "AI Document Type Classifier")
    add_row("Document Details", "Job Reference ID", doc_id, "100%", "Unique Processing Identifier")
    add_row("Document Details", "Overall OCR Confidence", overall_conf, overall_conf, "Confidence Metric")
    add_row("Document Details", "OCR Engine", engine, "100%", "Primary Extraction Engine")
    add_row("Document Details", "Processing Duration", proc_time, "100%", "Pipeline Duration")
    add_row("Document Details", "Language Detected", language, "100%", "Text Language")
    add_row("Document Details", "Processed Timestamp", timestamp, "100%", "Extraction Timestamp")

    # Image & File Specifications
    if img_info.get("file_size") and img_info["file_size"] != "N/A":
        add_row("Image & File Info", "File Size", img_info["file_size"], "100%", "Physical File Size")
    if img_info.get("format") and img_info["format"] != "Unknown":
        add_row("Image & File Info", "File Format", img_info["format"], "100%", "Detected Media Format")
    if img_info.get("dimensions") and img_info["dimensions"] != "N/A":
        add_row("Image & File Info", "Image Dimensions / Resolution", img_info["dimensions"], "100%", "Image Resolution / Page Count")
    if img_info.get("color_mode") and img_info["color_mode"] != "N/A":
        add_row("Image & File Info", "Color Mode", img_info["color_mode"], "100%", "Color Channel Specification")
    if img_info.get("dpi") and img_info["dpi"] != "N/A":
        add_row("Image & File Info", "Resolution DPI", img_info["dpi"], "100%", "Dots Per Inch")

    # 2. AI Executive Summary & Key Findings
    summary = job_data.get("summary") or job_data.get("ai_summary")
    if summary and str(summary).strip():
        add_row("AI Summary", "Executive Summary", summary, overall_conf, "AI Document Synthesis")

    ai_insights = job_data.get("ai_insights_structured")
    if isinstance(ai_insights, dict) and ai_insights.get("key_findings"):
        for idx, kf in enumerate(ai_insights["key_findings"]):
            add_row("AI Summary", f"Key Finding {idx+1}", kf, overall_conf, "Automated Key Finding")

    # 3. Key Extracted Fields & Structured Data
    fields = _get_fields_from_job(job_data)
    seen_fields = set()
    for f in fields:
        fname = f.get("name") or "Field"
        fval = f.get("value") or ""
        fconf = f.get("confidence") or overall_conf
        key_norm = f"{fname.lower()}:{str(fval).lower()}"
        if key_norm not in seen_fields:
            seen_fields.add(key_norm)
            add_row("Extracted Data", fname, fval, fconf, "Structured Extracted Field")

    # 4. Extracted Tables & Line Items
    tables = job_data.get("tables") or []
    for t_idx, table in enumerate(tables):
        t_label = f"Table {t_idx + 1}"
        if isinstance(table, dict):
            headers = table.get("headers") or []
            rows = table.get("rows") or []
            if headers and rows:
                for r_idx, row in enumerate(rows):
                    row_cells = row if isinstance(row, list) else [row]
                    for c_idx, cell in enumerate(row_cells):
                        h_name = headers[c_idx] if c_idx < len(headers) else f"Column {c_idx+1}"
                        add_row("Extracted Tables", f"{t_label} - Row {r_idx+1} [{h_name}]", cell, overall_conf, f"Line Item {r_idx+1}")
            elif rows:
                for r_idx, row in enumerate(rows):
                    row_cells = row if isinstance(row, list) else [row]
                    for c_idx, cell in enumerate(row_cells):
                        add_row("Extracted Tables", f"{t_label} - Row {r_idx+1} [Col {c_idx+1}]", cell, overall_conf, f"Line Item {r_idx+1}")
            elif table.get("row"):
                add_row("Extracted Tables", f"{t_label} - Row 1", table["row"], overall_conf, "Detected Table Line")
        elif isinstance(table, str) and table.strip():
            add_row("Extracted Tables", f"{t_label} - Line", table, overall_conf, "Raw Table Line")

    # 5. Named Entities
    entities = job_data.get("entities") or job_data.get("spacy_entities") or []
    if isinstance(entities, list):
        for e in entities:
            if isinstance(e, dict):
                label = e.get("label") or e.get("entity") or "ENTITY"
                val = e.get("value") or e.get("text") or ""
                e_conf = e.get("confidence") or overall_conf
                add_row("Named Entities", label.upper(), val, e_conf, "NLP Entity Recognition")

    # 6. Data Integrity & Validation
    validation = job_data.get("validation")
    if isinstance(validation, dict):
        if validation.get("passed_count") is not None:
            add_row("Integrity Verification", "Checks Passed", validation["passed_count"], "100%", "Math & Schema Rules Passed")
        if validation.get("warnings"):
            for w in validation["warnings"]:
                msg = w.get("message") if isinstance(w, dict) else str(w)
                add_row("Integrity Verification", "Validation Warning", msg, "Warning", "Rule Check Warning")

    df = pd.DataFrame(records)
    return df.to_csv(index=False)



def export_to_txt(job_data):
    """Export the currently processed document text without debug noise or object dumps."""
    if not isinstance(job_data, dict):
        return ""

    lines = []
    filename = job_data.get("filename") or "document"
    doc_type = job_data.get("document_type") or "General Document"
    lines.append(f"Document: {filename}")
    lines.append(f"Document Type: {doc_type}")

    summary = _safe_export_text(job_data.get("summary") or job_data.get("ai_summary"))
    if summary:
        lines.append("")
        lines.append("SUMMARY")
        lines.append(summary)

    raw_text = _safe_export_text(job_data.get("raw_text") or job_data.get("ocr_text") or "")
    formatted_text = _safe_export_text(job_data.get("display_formatted_text") or job_data.get("formatted_text") or "")
    structured_text = _safe_export_text(job_data.get("structured_data"))

    if raw_text:
        lines.append("")
        lines.append("RAW EXTRACTED TEXT")
        lines.append(raw_text)
    elif formatted_text:
        lines.append("")
        lines.append("FORMATTED TEXT")
        lines.append(formatted_text)

    if formatted_text and raw_text:
        lines.append("")
        lines.append("FORMATTED TEXT")
        lines.append(formatted_text)

    if structured_text:
        lines.append("")
        lines.append("STRUCTURED DATA")
        lines.append(structured_text)

    text = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", text)



def _format_confidence_str(job_data):
    conf = job_data.get('confidence_score') or job_data.get('confidence')
    if conf is None:
        return 'N/A'
    if isinstance(conf, str):
        s = conf.strip()
        return s if s.endswith('%') else f"{s}%"
    if isinstance(conf, (int, float)):
        v = conf * 100.0 if conf <= 1.0 else conf
        return f"{round(v, 1)}%"
    return str(conf)



def _get_fields_from_job(job_data):
    """Helper to extract structured fields list from job_data."""
    fields = []

    # Priority 1: extracted_fields
    raw_fields = job_data.get('extracted_fields')
    if isinstance(raw_fields, list) and len(raw_fields) > 0:
        for f in raw_fields:
            if isinstance(f, dict):
                fname = f.get('field_name') or f.get('field_key') or 'Field'
                fval = f.get('value', '')
                fconf = f.get('confidence', '')
                fields.append({'name': str(fname), 'value': str(fval), 'confidence': str(fconf)})

    # Priority 2: grouped_fields
    if not fields and isinstance(job_data.get('grouped_fields'), list):
        for group in job_data.get('grouped_fields'):
            for f in group.get('fields', []):
                if isinstance(f, dict):
                    fname = f.get('field_name', 'Field')
                    fval = f.get('value', '')
                    fconf = f.get('confidence', '')
                    fields.append({'name': str(fname), 'value': str(fval), 'confidence': str(fconf)})

    # Priority 3: structured_data
    if not fields and isinstance(job_data.get('structured_data'), dict):
        struct = job_data.get('structured_data')
        for k, v in struct.items():
            if k != 'confidence':
                fname = str(k).replace('_', ' ').title()
                fval = str(v) if v else 'N/A'
                fields.append({'name': fname, 'value': fval, 'confidence': 'N/A'})

    return fields


def export_to_docx(job_data):
    """
    Generates a compact DOCX document with proper structure:
    PAGE 1:
    - Title: Intelligent OCR Extraction Report
    - Document Information
    - AI Summary
    - Extracted Structured Data
    - AI Insights
    PAGE BREAK
    PAGE 2:
    - Formatted Text
    - Raw Extracted Text
    """
    doc = Document()

    # Document Margins
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # =====================================================
    # PAGE 1: ALL SUMMARY SECTIONS
    # =====================================================
    title_p = doc.add_paragraph()
    title_run = title_p.add_run('Intelligent OCR Extraction Report')
    title_run.bold = True
    title_run.font.size = Pt(20)
    title_run.font.color.rgb = RGBColor(30, 64, 175)
    title_p.paragraph_format.space_after = Pt(12)

    h1 = doc.add_heading('Document Information', level=2)
    h1.style.font.color.rgb = RGBColor(30, 64, 175)

    p_info = doc.add_paragraph()
    filename = job_data.get('filename', 'N/A')
    doc_type = job_data.get('document_type', 'Unknown')
    confidence = _format_confidence_str(job_data)
    timestamp = job_data.get('timestamp') or job_data.get('upload_time', 'N/A')
    engine = job_data.get('engine', 'PaddleOCR / Tesseract')

    p_info.add_run("Filename: ").bold = True
    p_info.add_run(f"{filename}\n")
    p_info.add_run("Document Type: ").bold = True
    p_info.add_run(f"{doc_type}\n")
    p_info.add_run("OCR Engine: ").bold = True
    p_info.add_run(f"{engine}\n")
    p_info.add_run("OCR Confidence: ").bold = True
    p_info.add_run(f"{confidence}\n")
    p_info.add_run("Processed On: ").bold = True
    p_info.add_run(f"{timestamp}")
    p_info.paragraph_format.space_after = Pt(14)

    # AI SUMMARY
    h2 = doc.add_heading('AI Summary', level=2)
    h2.style.font.color.rgb = RGBColor(30, 64, 175)
    summary_text = job_data.get('summary', 'No summary available.')
    p_sum = doc.add_paragraph(summary_text)
    p_sum.paragraph_format.space_after = Pt(14)

    # EXTRACTED STRUCTURED DATA
    h3 = doc.add_heading('Extracted Structured Data', level=2)
    h3.style.font.color.rgb = RGBColor(30, 64, 175)
    fields = _get_fields_from_job(job_data)

    if fields:
        table = doc.add_table(rows=1, cols=3)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Field Name'
        hdr_cells[1].text = 'Extracted Value'
        hdr_cells[2].text = 'Confidence'

        for cell in hdr_cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    r.bold = True
                    r.font.color.rgb = RGBColor(255, 255, 255)

        for cell in table.rows[0].cells:
            tcPr = cell._tc.get_or_add_tcPr()
            shd = tcPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd')
            if shd is None:
                from docx.oxml import OxmlElement
                from docx.oxml.ns import qn
                shd = OxmlElement('w:shd')
                shd.set(qn('w:val'), 'clear')
                shd.set(qn('w:color'), 'auto')
                shd.set(qn('w:fill'), '2563EB')
                tcPr.append(shd)

        for f in fields:
            row_cells = table.add_row().cells
            row_cells[0].text = f['name']
            row_cells[1].text = f['value'] or 'N/A'
            row_cells[2].text = f['confidence'] or 'N/A'
    else:
        doc.add_paragraph("No structured fields extracted.")

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # AI INSIGHTS
    h4 = doc.add_heading('AI Insights', level=2)
    h4.style.font.color.rgb = RGBColor(30, 64, 175)

    insights_added = False
    entities = job_data.get('entities') or job_data.get('spacy_entities')
    if isinstance(entities, list) and len(entities) > 0:
        p_ent = doc.add_paragraph()
        p_ent.add_run("Key Entities Detected:\n").bold = True
        for e in entities[:10]:
            label = e.get('label') or e.get('entity', 'Entity')
            val = e.get('value') or e.get('text', '')
            p_ent.add_run(f"• {label}: {val}\n")
        insights_added = True

    layout = job_data.get('layout_analysis')
    if isinstance(layout, dict):
        p_lay = doc.add_paragraph()
        p_lay.add_run("Layout Structure:\n").bold = True
        headings = layout.get('headings', [])
        if headings:
            p_lay.add_run(f"Headings Found: {', '.join(headings[:5])}\n")
        p_lay.add_run(f"Forms Detected: {'Yes' if layout.get('forms_detected') else 'No'}\n")
        p_lay.add_run(f"Tables Detected: {'Yes' if layout.get('tables_detected') else 'No'}\n")
        insights_added = True

    tables = job_data.get('tables')
    if isinstance(tables, list) and len(tables) > 0:
        p_tbl = doc.add_paragraph()
        p_tbl.add_run("Extracted Table Rows:\n").bold = True
        for t in tables[:5]:
            row_val = t.get('row') or str(t)
            p_tbl.add_run(f"• {row_val}\n")
        insights_added = True

    if not insights_added:
        doc.add_paragraph("No additional AI insights available for this document.")

    # Page break for second page
    doc.add_page_break()

    # =====================================================
    # PAGE 2: FORMATTED TEXT AND RAW TEXT
    # =====================================================
    h_fmt = doc.add_heading('Formatted Text', level=2)
    h_fmt.style.font.color.rgb = RGBColor(30, 64, 175)

    formatted_text = job_data.get('display_formatted_text') or job_data.get('formatted_text') or ''
    if formatted_text and formatted_text.strip():
        p_fmt = doc.add_paragraph()
        run_fmt = p_fmt.add_run(formatted_text)
        run_fmt.font.name = 'Courier New'
        run_fmt.font.size = Pt(9)
    else:
        doc.add_paragraph("No formatted text available.")

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    h_raw = doc.add_heading('Raw Extracted Text', level=2)
    h_raw.style.font.color.rgb = RGBColor(30, 64, 175)

    raw_text = job_data.get('raw_text', '')
    if raw_text and raw_text.strip():
        paragraphs = raw_text.split('\n')
        for line in paragraphs:
            if line.strip():
                doc.add_paragraph(line.strip())
    else:
        doc.add_paragraph("No raw OCR text available.")

    target = io.BytesIO()
    doc.save(target)
    return target.getvalue()


def export_to_pdf(job_data):
    """
    Generates a clean, professional, well-formatted report with proper sections,
    extracted data, tables, document details, and image information.
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("PDF export requires reportlab to be installed on the server.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=10
    )

    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1e40af'),
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1f2937')
    )

    summary_box_style = ParagraphStyle(
        'SummaryBox',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor('#1f2937')
    )

    formatted_text_style = ParagraphStyle(
        'FormattedText',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#1f2937'),
        leftIndent=0,
        spaceAfter=3
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#1f2937')
    )

    story = []

    # =====================================================
    # PAGE 1: DOCUMENT DETAILS, AI SUMMARY & STRUCTURED DATA
    # =====================================================
    story.append(Paragraph("INTELLIGENT OCR EXTRACTION REPORT", title_style))
    story.append(Spacer(1, 4))

    filename = job_data.get('filename', 'N/A')
    doc_type = job_data.get('document_type', 'Unknown')
    confidence = _format_confidence_str(job_data)
    timestamp = job_data.get('timestamp') or job_data.get('upload_time', 'N/A')
    engine = job_data.get('engine', 'PaddleOCR / WinOCR')
    proc_time = job_data.get('processing_time', 'N/A')
    lang = (job_data.get('detected_language') or 'English').title()

    img_info, img_path = _get_image_metadata(job_data)

    # Document & Image Specifications Grid Table
    info_table_data = [
        [
            Paragraph(f"<b>Filename:</b> {filename}<br/><b>Document Type:</b> {doc_type}<br/><b>Job Reference:</b> {job_data.get('job_id', 'N/A')}<br/><b>Processed On:</b> {timestamp}", body_style),
            Paragraph(f"<b>OCR Engine:</b> {engine}<br/><b>OCR Confidence:</b> <font color='#10b981'><b>{confidence}</b></font><br/><b>Image Specs:</b> {img_info.get('dimensions', 'N/A')} ({img_info.get('format', 'N/A')})<br/><b>File Size:</b> {img_info.get('file_size', 'N/A')} | <b>Lang:</b> {lang}", body_style)
        ]
    ]
    info_table = Table(info_table_data, colWidths=[270, 270])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 10))

    # AI SUMMARY
    story.append(Paragraph("AI SUMMARY", section_style))
    summary_text = job_data.get('summary') or job_data.get('ai_summary') or 'No summary available.'
    
    summary_table = Table([[Paragraph(summary_text, summary_box_style)]], colWidths=[540])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('LINELEFT', (0, 0), (0, -1), 3.5, colors.HexColor('#2563eb')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # EXTRACTED STRUCTURED DATA
    story.append(Paragraph("EXTRACTED STRUCTURED DATA", section_style))
    fields = _get_fields_from_job(job_data)

    if fields:
        table_data = [[
            Paragraph("Field Name", table_header_style),
            Paragraph("Extracted Value", table_header_style),
            Paragraph("Confidence", table_header_style)
        ]]

        for f in fields:
            table_data.append([
                Paragraph(f['name'], table_cell_style),
                Paragraph(f['value'] or 'N/A', table_cell_style),
                Paragraph(f['confidence'] or 'N/A', table_cell_style)
            ])

        t = Table(table_data, colWidths=[150, 310, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No structured fields extracted.", body_style))

    story.append(Spacer(1, 10))

    # EXTRACTED TABULAR DATA & AI INSIGHTS
    tables = job_data.get('tables') or []
    if tables:
        story.append(Paragraph("EXTRACTED TABULAR DATA", section_style))
        for t_idx, tbl in enumerate(tables[:3]):
            if isinstance(tbl, dict) and tbl.get('rows'):
                headers = tbl.get('headers') or []
                rows = tbl.get('rows') or []
                num_cols = max(len(headers), max((len(r) for r in rows if isinstance(r, list)), default=1))
                if num_cols > 0:
                    col_w = 540 / num_cols
                    table_rows = []
                    if headers:
                        table_rows.append([Paragraph(str(h), table_header_style) for h in headers])
                    for row in rows[:10]:
                        cells = row if isinstance(row, list) else [row]
                        table_rows.append([Paragraph(str(c or ''), table_cell_style) for c in cells])
                    
                    if table_rows:
                        pdf_tbl = Table(table_rows, colWidths=[col_w] * num_cols)
                        pdf_tbl.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                            ('TOPPADDING', (0, 0), (-1, -1), 4),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
                        ]))
                        story.append(pdf_tbl)
                        story.append(Spacer(1, 6))
            elif isinstance(tbl, dict) and tbl.get('row'):
                story.append(Paragraph(f"• {tbl['row']}", body_style))
        story.append(Spacer(1, 10))

    # AI INSIGHTS
    story.append(Paragraph("AI INSIGHTS", section_style))
    insights_lines = []

    entities = job_data.get('entities') or job_data.get('spacy_entities')
    if isinstance(entities, list) and len(entities) > 0:
        insights_lines.append("<b>Key Entities Detected:</b>")
        for e in entities[:8]:
            label = e.get('label') or e.get('entity', 'Entity')
            val = e.get('value') or e.get('text', '')
            insights_lines.append(f"• {label}: {val}")

    layout = job_data.get('layout_analysis')
    if isinstance(layout, dict):
        insights_lines.append("<br/><b>Layout Structure:</b>")
        headings = layout.get('headings', [])
        if headings:
            insights_lines.append(f"Headings Found: {', '.join(headings[:5])}")
        insights_lines.append(f"Forms Detected: {'Yes' if layout.get('forms_detected') else 'No'}")
        insights_lines.append(f"Tables Detected: {'Yes' if layout.get('tables_detected') else 'No'}")

    if insights_lines:
        story.append(Paragraph("<br/>".join(insights_lines), body_style))
    else:
        story.append(Paragraph("No additional AI insights available for this document.", body_style))

    story.append(Spacer(1, 10))

    # Page break for second page
    story.append(PageBreak())

    # =====================================================
    # PAGE 2: IMAGE PREVIEW, FORMATTED TEXT AND RAW TEXT
    # =====================================================
    # EMBED DOCUMENT IMAGE PREVIEW IF AVAILABLE
    if img_path and img_info.get("has_image"):
        try:
            from PIL import Image as PILImage
            with PILImage.open(img_path) as pim:
                pw, ph = pim.size
                aspect = ph / max(1, pw)
                target_w = min(360, pw)
                target_h = min(220, target_w * aspect)
                target_w = target_h / aspect
                
                story.append(Paragraph("DOCUMENT VISUAL PREVIEW", section_style))
                story.append(RLImage(img_path, width=target_w, height=target_h))
                story.append(Paragraph(f"<font size=7.5 color='#64748b'>Source: {filename} | Resolution: {img_info.get('dimensions', 'N/A')} | Format: {img_info.get('format', 'N/A')} | Color Mode: {img_info.get('color_mode', 'N/A')}</font>", body_style))
                story.append(Spacer(1, 10))
        except Exception:
            pass

    story.append(Paragraph("FORMATTED TEXT", section_style))
    formatted_text = job_data.get('display_formatted_text') or job_data.get('formatted_text') or ''
    
    if formatted_text and formatted_text.strip():
        lines = formatted_text.split('\n')
        for line in lines:
            if line.strip():
                escaped = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(escaped, formatted_text_style))
                story.append(Spacer(1, 2))
    else:
        story.append(Paragraph("No formatted text available.", body_style))

    story.append(Spacer(1, 15))

    story.append(Paragraph("RAW EXTRACTED TEXT", section_style))
    raw_text = job_data.get('raw_text', '')
    if raw_text and raw_text.strip():
        paragraphs = raw_text.split('\n')
        for line in paragraphs:
            if line.strip():
                escaped = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(escaped, body_style))
                story.append(Spacer(1, 3))
    else:
        story.append(Paragraph("No raw OCR text available.", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def export_to_excel(job_data):
    """Generates an Excel workbook (.xlsx) or CSV fallback from job_data."""
    fields = _get_fields_from_job(job_data)

    meta = [
        {"Property": "Filename", "Value": job_data.get("filename", "N/A")},
        {"Property": "Document Type", "Value": job_data.get("document_type", "N/A")},
        {"Property": "Job ID", "Value": job_data.get("job_id") or job_data.get("id", "N/A")},
        {"Property": "Upload Time", "Value": job_data.get("upload_time") or job_data.get("timestamp", "N/A")},
        {"Property": "OCR Engine", "Value": job_data.get("engine", "PaddleOCR")},
        {"Property": "Confidence Score", "Value": _format_confidence_str(job_data)},
        {"Property": "Summary", "Value": job_data.get("summary", "N/A")}
    ]

    meta_df = pd.DataFrame(meta)
    fields_df = pd.DataFrame(fields) if fields else pd.DataFrame([{"name": "N/A", "value": "N/A", "confidence": "N/A"}])

    buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            meta_df.to_excel(writer, sheet_name='Overview', index=False)
            fields_df.to_excel(writer, sheet_name='Extracted Fields', index=False)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception:
        csv_str = export_to_csv(fields)
        return csv_str.encode('utf-8')


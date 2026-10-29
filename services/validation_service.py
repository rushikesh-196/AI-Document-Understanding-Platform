"""
Validation Layer for AI Document Extraction
Cross-validates extracted fields, line items, mathematical calculations, and formats.
Attaches validation flags/warnings without mutating true extracted text.
"""

import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^(?:\+?\d{1,4}[\s.-]?)?\(?\d{2,5}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,6}$")
GST_REGEX = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z0-9]{1}Z[A-Z0-9]{1}$")
PAN_REGEX = re.compile(r"^[A-Z]{5}\d{4}[A-Z]{1}$")


def _parse_float(val):
    """Safely parse numbers with commas, currency symbols, etc."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).strip()
        # Remove currency symbols and formatting commas
        s_clean = re.sub(r"[^\d.-]", "", s)
        if s_clean and s_clean not in ("-", "."):
            return float(s_clean)
    except Exception:
        pass
    return None


def validate_email_format(email_str):
    if not email_str:
        return True, None
    if EMAIL_REGEX.match(str(email_str).strip()):
        return True, "Valid email format"
    return False, f"Invalid email format: '{email_str}'"


def validate_phone_format(phone_str):
    if not phone_str:
        return True, None
    clean = re.sub(r"[\s()-]", "", str(phone_str).strip())
    if len(clean) >= 7 and (clean.isdigit() or (clean.startswith("+") and clean[1:].isdigit())):
        return True, "Valid phone format"
    return False, f"Unrecognized phone number format: '{phone_str}'"


def validate_gst_format(gst_str):
    if not gst_str:
        return True, None
    clean = str(gst_str).strip().upper()
    if GST_REGEX.match(clean):
        return True, "Valid GSTIN format"
    return False, f"GSTIN '{clean}' does not match standard 15-character Indian GST format"


def validate_date_format(date_str):
    if not date_str:
        return True, None
    s = str(date_str).strip()
    date_formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y",
        "%Y/%m/%d", "%d.%m.%Y", "%B %d, %Y", "%b %d, %Y",
        "%d %B %Y", "%d %b %Y", "%Y-%m-%dT%H:%M:%S"
    ]
    for fmt in date_formats:
        try:
            datetime.strptime(s, fmt)
            return True, "Valid date format"
        except ValueError:
            pass
    # If standard parsing fails, check if year looks reasonable
    if re.search(r"\b(19|20)\d{2}\b", s):
        return True, "Date contains valid year"
    return False, f"Date '{date_str}' format could not be verified"


def validate_extracted_data(extracted_fields, structured_data=None, tables=None, doc_type="General Document"):
    """
    Comprehensive document validation layer.
    Returns:
        validations: dict with overall status, warnings list, passed checks list, and annotated fields.
    """
    warnings = []
    passed = []
    field_validations = {}

    structured = structured_data or {}

    # 1. Line items math check (quantity * rate ≈ amount)
    if tables:
        for t_idx, table in enumerate(tables):
            rows = table.get("rows", [])
            for r_idx, row in enumerate(rows):
                if isinstance(row, dict):
                    qty = _parse_float(row.get("quantity") or row.get("qty"))
                    rate = _parse_float(row.get("rate") or row.get("price") or row.get("unit_price"))
                    amt = _parse_float(row.get("amount") or row.get("total"))
                    desc = row.get("description") or row.get("item") or f"Item {r_idx + 1}"
                    if qty is not None and rate is not None and amt is not None:
                        calc_amt = round(qty * rate, 2)
                        diff = abs(calc_amt - amt)
                        if diff > 0.05 and (diff / max(1.0, amt)) > 0.02:
                            w_msg = f"Table {t_idx + 1}, {desc}: Qty ({qty}) × Rate ({rate}) = {calc_amt}, does not match Amount ({amt})"
                            warnings.append({"field": "line_item", "message": w_msg, "severity": "warning"})
                        else:
                            passed.append(f"Line item math verified for {desc}: {qty} × {rate} = {amt}")
                elif isinstance(row, list) and len(row) >= 3:
                    nums = [_parse_float(c) for c in row if _parse_float(c) is not None]
                    if len(nums) >= 3:
                        q, r, a = nums[0], nums[1], nums[2]
                        if abs(round(q * r, 2) - a) < 0.05:
                            passed.append(f"Row {r_idx + 1} calculation verified: {q} × {r} = {a}")

    # 2. Total math checks: subtotal + tax ≈ total_amount
    subtotal = _parse_float(structured.get("subtotal"))
    tax = _parse_float(structured.get("tax") or structured.get("tax_amount") or structured.get("gst_amount"))
    total = _parse_float(structured.get("total_amount") or structured.get("grand_total") or structured.get("total"))

    if subtotal is not None and tax is not None and total is not None:
        calc_total = round(subtotal + tax, 2)
        diff = abs(calc_total - total)
        if diff > 0.10 and (diff / max(1.0, total)) > 0.02:
            w_msg = f"Calculated total (Subtotal {subtotal} + Tax {tax} = {calc_total}) does not match Total Amount ({total})"
            warnings.append({"field": "total_amount", "message": w_msg, "severity": "warning"})
            field_validations["total_amount"] = {"status": "warning", "message": w_msg}
        else:
            passed.append(f"Document total verified: Subtotal ({subtotal}) + Tax ({tax}) = Total ({total})")
            field_validations["total_amount"] = {"status": "valid", "message": "Total matches Subtotal + Tax"}

    # 3. Format validations on extracted fields
    if isinstance(extracted_fields, list):
        for field in extracted_fields:
            if not isinstance(field, dict):
                continue
            k = str(field.get("name") or field.get("field") or field.get("key", "")).lower()
            val = field.get("value")
            if val is None or str(val).strip() == "" or str(val).lower() in ("null", "none", "not_detected"):
                field["source"] = field.get("source", "not_detected")
                field["confidence"] = field.get("confidence", 0.0)
                continue

            val_str = str(val).strip()

            # Email check
            if "email" in k:
                is_valid, msg = validate_email_format(val_str)
                if not is_valid:
                    warnings.append({"field": k, "message": msg, "severity": "warning"})
                    field["validation"] = {"status": "warning", "message": msg}
                else:
                    passed.append(f"Field '{k}' has valid email format")
                    field["validation"] = {"status": "valid", "message": msg}

            # Phone check
            elif any(p in k for p in ["phone", "mobile", "contact", "tel"]):
                is_valid, msg = validate_phone_format(val_str)
                if not is_valid:
                    warnings.append({"field": k, "message": msg, "severity": "warning"})
                    field["validation"] = {"status": "warning", "message": msg}
                else:
                    passed.append(f"Field '{k}' has valid phone format")
                    field["validation"] = {"status": "valid", "message": msg}

            # GST check
            elif any(g in k for g in ["gst", "gstin"]):
                is_valid, msg = validate_gst_format(val_str)
                if not is_valid:
                    warnings.append({"field": k, "message": msg, "severity": "warning"})
                    field["validation"] = {"status": "warning", "message": msg}
                else:
                    passed.append(f"Field '{k}' has valid GSTIN format")
                    field["validation"] = {"status": "valid", "message": msg}

            # PAN check
            elif "pan" in k:
                if PAN_REGEX.match(val_str.upper()):
                    passed.append(f"Field '{k}' has valid PAN format")
                    field["validation"] = {"status": "valid", "message": "Valid PAN format"}
                else:
                    w = f"PAN '{val_str}' does not match standard 10-character alphanumeric PAN format"
                    warnings.append({"field": k, "message": w, "severity": "warning"})
                    field["validation"] = {"status": "warning", "message": w}

            # Date check
            elif "date" in k:
                is_valid, msg = validate_date_format(val_str)
                if not is_valid:
                    warnings.append({"field": k, "message": msg, "severity": "warning"})
                    field["validation"] = {"status": "warning", "message": msg}
                else:
                    passed.append(f"Field '{k}' has valid date format")
                    field["validation"] = {"status": "valid", "message": msg}

    status = "warning" if len(warnings) > 0 else "valid"

    return {
        "status": status,
        "warning_count": len(warnings),
        "passed_count": len(passed),
        "warnings": warnings,
        "passed": passed,
        "field_validations": field_validations,
    }

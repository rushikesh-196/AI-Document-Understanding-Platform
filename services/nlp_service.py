"""
Comprehensive Dynamic Information Extraction Service
Supports: Receipt, Invoice, Business Card, Resume, ID Card,
          Medical Report, Bank Statement, Passport, Driving License, Utility Bill, Purchase Order
"""

import logging
import re
import spacy
from services.llm_service import is_llm_available, extract_information_with_llm

logger = logging.getLogger(__name__)
_nlp_model = None


def get_spacy_model():
    """Singleton getter for spaCy NLP model to avoid repeated loading."""
    global _nlp_model
    if _nlp_model is None:
        try:
            _nlp_model = spacy.load("en_core_web_sm")
        except Exception:
            try:
                spacy.cli.download("en_core_web_sm")
                _nlp_model = spacy.load("en_core_web_sm")
            except Exception as e:
                logger.debug("spaCy model download error: %s", e)
                _nlp_model = False
    return _nlp_model


# ─────────────────────────────────────────────────────────────────────────────
# UI/NOISE FILTERS
# ─────────────────────────────────────────────────────────────────────────────

INVALID_ENTITY_TOKENS = {
    "home", "upload", "results", "history", "about", "login", "register",
    "extract doc", "enterprise ai document intelligence", "ai-powered intelligent",
    "ocr & entity extraction", "automated ocr pipeline", "view demo results",
    "platform features", "secure file handling", "dual ocr engines",
    "spacy nlp extraction", "multi-format exports", "intelligent ocr",
    "dashboard", "contact", "experience", "projects", "education", "certifications",
    "invoice", "receipt", "document", "amount", "total", "subtotal",
    "rs", "inr", "usd", "eur", "street,city,country", "street,city", "country",
    "support", "details such as support", "n/a", "null", "none", "undefined",
    "00000", "123 name st., city, 00000", "street", "city"
}


def is_valid_entity_text(val):
    if not val or not str(val).strip():
        return False
    clean_val = str(val).strip().lower()
    if clean_val in INVALID_ENTITY_TOKENS:
        return False
    if any(noise in clean_val for noise in ["deskew ->", "spacy ner", "ocr accuracy", "processing time", "automated ocr", "street,city,country"]):
        return False
    if len(clean_val) < 2:
        return False
    if re.match(r'^\d{1,3}$', clean_val):
        return False
    return True


def _clean(val):
    """Strip and collapse whitespace."""
    return re.sub(r'\s+', ' ', str(val)).strip()


# ─────────────────────────────────────────────────────────────────────────────
# REGEX PATTERNS — Precision-tuned for accurate field extraction
# ─────────────────────────────────────────────────────────────────────────────

PATTERNS = {
    # ── Universal ──────────────────────────────────────────────────────────
    "email": r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    "phone": r"(?:Phone|Mobile|Tel|Contact|Mob\.?)?[:\s]*(?P<ph>\+?[0-9]{1,4}[\s\-\.]?\(?[0-9]{3,5}\)?[\s\-\.]?[0-9]{3,5}[\s\-\.]?[0-9]{3,5})(?!\d)",
    "website": r"https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?|www\.[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    "date": r"\b(?:\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\b",
    "currency": r"\b(USD|INR|EUR|GBP|AUD|CAD)\b",
    "pin_code": r"(?:PIN|ZIP|Pincode|Postal\s*Code)[:\s]*(\b\d{6}\b)|\b(\d{6})\b(?=\s|$)",
    "zip_code": r"\b(\d{5}(?:-\d{4})?)\b",

    # ── Receipt / Invoice ───────────────────────────────────────────────────
    "invoice_number": r"(?:Invoice\s*(?:No\.?|#|Number|ID)?|INV[-#\s]?|Bill\s*(?:No\.?|#)?)[:\s#]*([A-Z0-9][-A-Z0-9/]{3,20})",
    "receipt_number": r"(?:Receipt\s*(?:No\.?|#)?|Rec(?:eipt)?\s*#?|Txn\s*(?:Id|No)?)[:\s]*([A-Z0-9][-A-Z0-9/]{3,20})",
    "order_number": r"(?:Order\s*(?:No\.?|#)?|PO\s*(?:No\.?|#)?)[:\s]*([A-Z0-9][-A-Z0-9/]{3,20})",
    "due_date": r"(?:Due\s*Date|Payment\s*Due|Due\s*By)[:\s]*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})",
    "subtotal": r"(?:Subtotal|Sub\s*Total)[:\s]*(?:Rs\.?|₹|INR|\$|€|£)?\s*([0-9,]+\.?[0-9]*)",
    "tax": r"(?:Tax|VAT|GST|CGST|SGST|IGST|Service\s*Tax)\s*\([^)]*\)[:\s]*(?:Rs\.?|₹|INR|\$|€|£)?\s*([0-9,]+\.[0-9]{2})|(?:Tax|VAT|GST|CGST|SGST|IGST|Service\s*Tax)[:\s]*(?:Rs\.?|₹|INR|\$|€|£)\s*([0-9,]+\.?[0-9]*)",
    "total_amount": r"(?:Total\s*Amount|Grand\s*Total|Total\s*Due|Total\s*Paid|Net\s*Total|Amount\s*Due|Balance\s*Due)[:\s]*(?:Rs\.?|₹|INR|\$|€|£)?\s*([0-9,]+\.[0-9]{1,2})",
    "payment_method": r"(?:Payment\s*(?:Mode|Method|Type)|Paid\s*Via|Paid\s*By)[:\s]*(Cash|Card|UPI|Net\s*Banking|Cheque|Online|Credit\s*Card|Debit\s*Card|NEFT|RTGS|IMPS)",

    # ── Government ID & Tax ─────────────────────────────────────────────────
    "gst_number": r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z0-9]{1}Z[A-Z0-9]{1}\b",
    "pan_number": r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",
    "aadhaar_number": r"\b\d{4}\s?\d{4}\s?\d{4}\b",
    "date_of_birth": r"(?:Date\s*of\s*Birth|DOB|Birth\s*Date|Born)[:\s]*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})",
    "id_number": r"(?:ID\s*(?:No\.?|Number|#)|Card\s*(?:No\.?|Number)|Enrollment\s*(?:No\.?|Number)|Roll\s*(?:No\.?|Number)|Registration\s*(?:No\.?))[:\s]*([A-Z0-9][-A-Z0-9/]{4,20})",
    "gender": r"(?:Gender|Sex)[:\s]*(Male|Female|M|F|Other|Transgender)",
    "blood_group": r"\b(A|B|AB|O)[+\-](?=\b|\s)",
    "nationality": r"(?:Nationality|Citizen\s*of)[:\s]*([A-Za-z]+(?:\s+[A-Za-z]+)?)",
    "expiry_date": r"(?:Expiry|Expiration|Valid\s*(?:Until|Till|Through)|Expires?)[:\s]*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})",

    # ── Resume / CV ─────────────────────────────────────────────────────────
    "job_title": r"(?:(?:Senior|Junior|Lead|Principal|Associate|Chief|Head|VP|Vice\s*President|Executive|Managing|General)?\s*(?:Software\s*Engineer|Engineer|Developer|Designer|Manager|Director|Analyst|Consultant|Architect|Officer|Specialist|Coordinator|Executive|CEO|CTO|CFO|COO|President|Founder|Partner|Advisor|Professor|Doctor))",
    "skills": r"(?:Skills?|Technical\s*Skills?|Core\s*Competencies?|Expertise)[:\s\n]*((?:[A-Za-z0-9#+.\-]+(?:[,/\n]\s*)?){3,})",
    "experience_years": r"(\d+\+?\s*years?\s*(?:of\s*)?(?:experience|exp\.))",
    "degree": r"\b(Bachelor(?:'s)?|Master(?:'s)?|B\.?Tech|M\.?Tech|B\.?E|M\.?E|B\.?Sc|M\.?Sc|MBA|PhD|Ph\.D|B\.?Com|M\.?Com|BCA|MCA|Diploma)\b",

    # ── Bank Statement ──────────────────────────────────────────────────────
    "account_number": r"(?:Acct\.?\s*(?:No\.?|Number)|Account\s*(?:No\.?|Number|#))[:\s]*([\dX*]{4,20})",
    "ifsc_code": r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    "opening_balance": r"(?:Opening\s*Balance|Beginning\s*Balance)[:\s]*(?:Rs\.?|₹|INR|\$|€|£)?\s*([0-9,]+\.?[0-9]*)",
    "closing_balance": r"(?:Closing\s*Balance|Ending\s*Balance|Available\s*Balance)[:\s]*(?:Rs\.?|₹|INR|\$|€|£)?\s*([0-9,]+\.?[0-9]*)",

    # ── Medical Report ──────────────────────────────────────────────────────
    "patient_name": r"(?:Patient(?:\s*Name)?|Patient\s*Information)[:\s]+([A-Za-z\s\.]{2,40})(?:\n|$)",
    "doctor_name": r"(?:Doctor(?:\s*Name)?|Dr\.?|Physician|Surgeon)[:\s]+([A-Za-z\s\.]{2,40})(?:\n|$)",
    "diagnosis": r"(?:Diagnosis|Finding|Impression|Condition)[:\s]+([^\n\.]{3,80})(?:\n|\.|$)",

    # ── Address components ──────────────────────────────────────────────────
    "city": r"(?:City|Town)[:\s]*([A-Za-z\s]+?)(?:,|\n|$)",
    "state": r"(?:State|Province|Region)[:\s]*([A-Za-z\s]+?)(?:,|\n|$)",
    "country": r"(?:Country)[:\s]*([A-Za-z\s]+?)(?:,|\n|$)",
}

FIELD_METADATA = {
    "name":             {"label": "Name",              "icon": "fa-user"},
    "customer_name":    {"label": "Customer Name",     "icon": "fa-user-check"},
    "patient_name":     {"label": "Patient Name",      "icon": "fa-hospital-user"},
    "doctor_name":      {"label": "Doctor / Physician","icon": "fa-user-doctor"},
    "company":          {"label": "Company",           "icon": "fa-building"},
    "vendor_name":      {"label": "Vendor Name",       "icon": "fa-store"},
    "email":            {"label": "Email Address",     "icon": "fa-envelope"},
    "phone":            {"label": "Phone Number",      "icon": "fa-phone"},
    "website":          {"label": "Website",           "icon": "fa-globe"},
    "date":             {"label": "Date",              "icon": "fa-calendar"},
    "due_date":         {"label": "Due Date",          "icon": "fa-calendar-xmark"},
    "date_of_birth":    {"label": "Date of Birth",     "icon": "fa-cake-candles"},
    "amount":           {"label": "Amount",            "icon": "fa-dollar-sign"},
    "total_amount":     {"label": "Total Amount",      "icon": "fa-money-bill-wave"},
    "subtotal":         {"label": "Subtotal",          "icon": "fa-calculator"},
    "tax":              {"label": "Tax / GST / VAT",   "icon": "fa-percent"},
    "invoice_number":   {"label": "Invoice Number",    "icon": "fa-hashtag"},
    "receipt_number":   {"label": "Receipt Number",    "icon": "fa-receipt"},
    "order_number":     {"label": "Order / PO Number", "icon": "fa-cart-shopping"},
    "id_number":        {"label": "ID Number",         "icon": "fa-id-card"},
    "gst_number":       {"label": "GST Number",        "icon": "fa-building-flag"},
    "pan_number":       {"label": "PAN Number",        "icon": "fa-address-card"},
    "aadhaar_number":   {"label": "Aadhaar Number",    "icon": "fa-fingerprint"},
    "account_number":   {"label": "Account Number",    "icon": "fa-piggy-bank"},
    "ifsc_code":        {"label": "IFSC Code",         "icon": "fa-building-columns"},
    "opening_balance":  {"label": "Opening Balance",   "icon": "fa-wallet"},
    "closing_balance":  {"label": "Closing Balance",   "icon": "fa-coins"},
    "payment_method":   {"label": "Payment Method",    "icon": "fa-credit-card"},
    "job_title":        {"label": "Job Title",         "icon": "fa-briefcase"},
    "skills":           {"label": "Skills",            "icon": "fa-code"},
    "education":        {"label": "Education",         "icon": "fa-graduation-cap"},
    "degree":           {"label": "Degree",            "icon": "fa-certificate"},
    "diagnosis":        {"label": "Clinical Diagnosis","icon": "fa-stethoscope"},
    "address":          {"label": "Address",           "icon": "fa-location-dot"},
    "city":             {"label": "City",              "icon": "fa-city"},
    "state":            {"label": "State",             "icon": "fa-map"},
    "pin_code":         {"label": "PIN / ZIP Code",    "icon": "fa-map-pin"},
    "gender":           {"label": "Gender",            "icon": "fa-venus-mars"},
    "blood_group":      {"label": "Blood Group",       "icon": "fa-droplet"},
    "nationality":      {"label": "Nationality",       "icon": "fa-flag"},
}

FIELD_PRIORITY = [
    "invoice_number", "receipt_number", "order_number", "id_number", "gst_number", "pan_number", "aadhaar_number",
    "total_amount", "subtotal", "tax", "opening_balance", "closing_balance",
    "date", "due_date", "date_of_birth",
    "customer_name", "patient_name", "doctor_name", "name", "vendor_name", "company",
    "email", "phone", "website", "address", "city", "state", "pin_code",
    "job_title", "skills", "degree", "education", "diagnosis", "payment_method", "gender"
]


def _validate_invoice_number(val):
    if not val or len(val) < 3:
        return False
    if not re.search(r'\d', val):
        return False
    if val.lower() in INVALID_ENTITY_TOKENS:
        return False
    return True


def _validate_company_name(val):
    if not val or len(val) < 2:
        return None
    val_clean = val.strip()
    if val_clean.lower() in INVALID_ENTITY_TOKENS:
        return None
    return val_clean


def extract_information(text, ocr_confidence=92.0):
    """
    Unified extraction pipeline:
    - High-precision Regex patterns
    - Contextual keyword matchers
    - spaCy Named Entity Recognition (PERSON, ORG, GPE, DATE, MONEY)
    - Returns structured_data, extracted_fields_list, spacy_entities, summary.
    """
    if not text or not str(text).strip():
        return {
            "structured_data": {},
            "extracted_fields_list": [],
            "spacy_entities": [],
            "summary": "No text detected in document."
        }

    extracted = {}
    field_confidences = {}

    # 1. Regex Pattern Extractions
    for key, pattern in PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            val = match.group("ph") if ("ph" in match.groupdict() and match.group("ph")) else (match.group(1) if match.groups() else match.group(0))
            if val and str(val).strip():
                clean_v = _clean(val)
                if key == "phone":
                    digits = re.sub(r'\D', '', clean_v)
                    if len(digits) < 8 or len(digits) > 15:
                        continue
                if key == "invoice_number" and not _validate_invoice_number(clean_v):
                    continue
                extracted[key] = clean_v
                field_confidences[key] = min(99.0, ocr_confidence + 2.0)

    # 2. Contextual Names & Entities
    if "customer_name" not in extracted:
        c_match = re.search(r"(?:Bill(?:ed)?\s*To|Ship\s*To|Customer\s*(?:Name)?|Client\s*(?:Name)?)[:\s]+([A-Z][a-zA-Z\s]{2,35}?)(?:\n|$)", text, re.IGNORECASE)
        if c_match:
            cname = _clean(c_match.group(1))
            if len(cname) > 2 and cname.lower() not in INVALID_ENTITY_TOKENS:
                extracted["customer_name"] = cname
                field_confidences["customer_name"] = ocr_confidence

    if "vendor_name" not in extracted and "company" not in extracted:
        v_match = re.search(r"(?:Company|Organization|Org|From|Seller|Vendor|Issued\s*By|Store\s*Name)[:\s]+([A-Z][a-zA-Z\s&\.,]{2,40}?)(?:\n|$)", text, re.IGNORECASE)
        if v_match:
            vname = _clean(v_match.group(1))
            if vname.lower() not in INVALID_ENTITY_TOKENS:
                extracted["vendor_name"] = vname
                extracted["company"] = vname
                field_confidences["company"] = ocr_confidence

    # 3. spaCy Named Entity Recognition
    nlp = get_spacy_model()
    spacy_entities = []

    if nlp:
        doc = nlp(text[:6000])
        seen_ents = set()
        for ent in doc.ents:
            et = _clean(ent.text)
            if not is_valid_entity_text(et):
                continue
            if et.lower() in seen_ents:
                continue
            seen_ents.add(et.lower())
            spacy_entities.append({"text": et, "label": ent.label_})

            if ent.label_ == "PERSON" and "name" not in extracted and "customer_name" not in extracted:
                if len(et.split()) >= 2:
                    extracted["name"] = et
                    field_confidences["name"] = ocr_confidence
            elif ent.label_ == "ORG" and "company" not in extracted:
                clean_comp = _validate_company_name(et)
                if clean_comp:
                    extracted["company"] = clean_comp
                    field_confidences["company"] = ocr_confidence
            elif ent.label_ in ["GPE", "LOC"] and "address" not in extracted:
                extracted["address"] = et
                field_confidences["address"] = ocr_confidence
            elif ent.label_ == "DATE" and "date" not in extracted:
                if re.search(r'\d', et):
                    extracted["date"] = et
                    field_confidences["date"] = ocr_confidence
            elif ent.label_ == "MONEY" and "total_amount" not in extracted:
                extracted["total_amount"] = et
                field_confidences["total_amount"] = ocr_confidence

    # 4. Build extracted_fields_list
    extracted_fields_list = []
    seen_keys = set()

    for key in FIELD_PRIORITY:
        if key in extracted and key not in seen_keys:
            val = extracted[key]
            if val and str(val).strip():
                meta = FIELD_METADATA.get(key, {
                    "label": key.replace('_', ' ').title(),
                    "icon": "fa-tag"
                })
                fc = round(field_confidences.get(key, ocr_confidence), 1)
                extracted_fields_list.append({
                    "field_key": key,
                    "field_name": meta["label"],
                    "value": str(val).strip(),
                    "confidence": f"{fc}%",
                    "icon": meta["icon"]
                })
                seen_keys.add(key)

    for key, val in extracted.items():
        if key not in seen_keys and val and str(val).strip():
            meta = FIELD_METADATA.get(key, {
                "label": key.replace('_', ' ').title(),
                "icon": "fa-tag"
            })
            fc = round(field_confidences.get(key, ocr_confidence), 1)
            extracted_fields_list.append({
                "field_key": key,
                "field_name": meta["label"],
                "value": str(val).strip(),
                "confidence": f"{fc}%",
                "icon": meta["icon"]
            })

    return {
        "structured_data": extracted,
        "extracted_fields_list": extracted_fields_list,
        "spacy_entities": spacy_entities,
    }

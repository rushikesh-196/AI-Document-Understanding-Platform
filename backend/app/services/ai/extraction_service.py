"""
Information Extraction Service
Extracts key fields based on document type: Invoice, Resume, Bank Statement, Government IDs, Medical Reports
"""
import logging
import re
from typing import Dict, List, Any
from app.models.document import DocumentType

logger = logging.getLogger(__name__)


class InformationExtractionService:
    def __init__(self):
        pass
    
    def extract_information(self, text: str, document_type: DocumentType, 
                            entities: List[Dict]) -> Dict[str, Any]:
        """
        Extract key information based on document type
        
        Args:
            text: OCR text
            document_type: Classified document type
            entities: Named entities from NER
            
        Returns:
            Dictionary with extracted data, confidence, missing fields, and warnings
        """
        try:
            if document_type == DocumentType.INVOICE:
                return self._extract_invoice_info(text, entities)
            elif document_type == DocumentType.RESUME:
                return self._extract_resume_info(text, entities)
            elif document_type == DocumentType.BANK_STATEMENT:
                return self._extract_bank_statement_info(text, entities)
            elif document_type in [DocumentType.PASSPORT, DocumentType.AADHAAR, 
                                   DocumentType.PAN_CARD, DocumentType.DRIVING_LICENSE]:
                return self._extract_government_id_info(text, entities, document_type)
            elif document_type == DocumentType.MEDICAL_REPORT:
                return self._extract_medical_report_info(text, entities)
            else:
                return self._extract_generic_info(text, entities)
                
        except Exception as e:
            logger.error(f"Information extraction failed: {e}")
            return {
                "extracted_data": {},
                "confidence": 0.0,
                "missing_fields": [],
                "warnings": ["Extraction failed"]
            }
    
    def _extract_invoice_info(self, text: str, entities: List[Dict]) -> Dict[str, Any]:
        """Extract invoice-specific fields"""
        extracted = {}
        missing_fields = []
        warnings = []
        
        # Invoice Number
        invoice_match = re.search(
            r'(?:Invoice|Inv|Bill)\s*(?:No|Number|#)?\s*[:.]?\s*([\w\d\-/]+)',
            text, re.IGNORECASE
        )
        extracted["invoice_number"] = invoice_match.group(1) if invoice_match else None
        if not extracted["invoice_number"]:
            missing_fields.append("invoice_number")
        
        # Date
        date_match = re.search(
            r'(?:Date|Dated|Due\s*Date)?\s*[:.]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            text, re.IGNORECASE
        )
        extracted["date"] = date_match.group(1) if date_match else None
        if not extracted["date"]:
            missing_fields.append("date")
        
        # Due Date
        due_date_match = re.search(
            r'Due\s*Date\s*[:.]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            text, re.IGNORECASE
        )
        extracted["due_date"] = due_date_match.group(1) if due_date_match else None
        
        # Seller/Vendor
        seller_match = re.search(
            r'(?:From|Seller|Vendor|Bill\s*From)\s*[:.]?\s*([^\n]+)',
            text, re.IGNORECASE
        )
        extracted["seller"] = seller_match.group(1).strip() if seller_match else None
        if not extracted["seller"]:
            missing_fields.append("seller")
        
        # Buyer/Customer
        buyer_match = re.search(
            r'(?:To|Bill\s*To|Customer|Client)\s*[:.]?\s*([^\n]+)',
            text, re.IGNORECASE
        )
        extracted["buyer"] = buyer_match.group(1).strip() if buyer_match else None
        if not extracted["buyer"]:
            missing_fields.append("buyer")
        
        # GST Number
        gst_match = re.search(
            r'\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b',
            text
        )
        extracted["gst_number"] = gst_match.group() if gst_match else None
        
        # Tax
        tax_matches = re.findall(
            r'(?:Tax|GST|VAT|CGST|SGST|IGST)\s*[:.]?\s*[\₹$€£]?\s*([\d,]+\.?\d*)',
            text, re.IGNORECASE
        )
        extracted["tax"] = tax_matches[0] if tax_matches else None
        
        # Total Amount
        total_match = re.search(
            r'(?:Total|Grand\s*Total|Amount\s*Due)\s*[:.]?\s*[\₹$€£]?\s*([\d,]+\.?\d*)',
            text, re.IGNORECASE
        )
        extracted["total"] = total_match.group(1) if total_match else None
        if not extracted["total"]:
            missing_fields.append("total")
            warnings.append("Total amount not found")
        
        # Calculate confidence
        filled_fields = sum(1 for v in extracted.values() if v is not None)
        total_fields = len(extracted)
        confidence = filled_fields / total_fields if total_fields > 0 else 0.0
        
        return {
            "extracted_data": extracted,
            "confidence": confidence,
            "missing_fields": missing_fields,
            "warnings": warnings
        }
    
    def _extract_resume_info(self, text: str, entities: List[Dict]) -> Dict[str, Any]:
        """Extract resume-specific fields"""
        extracted = {}
        missing_fields = []
        warnings = []
        
        # Name (usually first line or from entities)
        name_entity = next((e for e in entities if e["label"] == "Person"), None)
        extracted["name"] = name_entity["text"] if name_entity else None
        if not extracted["name"]:
            # Try first line
            lines = text.split('\n')
            if lines:
                extracted["name"] = lines[0].strip()
        if not extracted["name"]:
            missing_fields.append("name")
        
        # Email
        email_entity = next((e for e in entities if e["label"] == "Email"), None)
        extracted["email"] = email_entity["text"] if email_entity else None
        if not extracted["email"]:
            missing_fields.append("email")
        
        # Phone
        phone_entity = next((e for e in entities if e["label"] == "Phone"), None)
        extracted["phone"] = phone_entity["text"] if phone_entity else None
        if not extracted["phone"]:
            missing_fields.append("phone")
        
        # Skills (extract from skills section)
        skills_section = re.search(
            r'(?:Skills|Technical\s*Skills|Core\s*Competencies)\s*[:.]?\s*([^\n]+(?:\n[^\n]+)*)',
            text, re.IGNORECASE
        )
        if skills_section:
            skills_text = skills_section.group(1)
            extracted["skills"] = [s.strip() for s in re.split(r'[,•\n]', skills_text) if s.strip()]
        else:
            extracted["skills"] = []
            missing_fields.append("skills")
        
        # Education
        education_section = re.search(
            r'(?:Education|Academic\s*Background|Qualification)\s*[:.]?\s*([^\n]+(?:\n[^\n]+)*)',
            text, re.IGNORECASE
        )
        extracted["education"] = education_section.group(1).strip() if education_section else None
        if not extracted["education"]:
            missing_fields.append("education")
        
        # Experience
        experience_section = re.search(
            r'(?:Experience|Work\s*History|Employment)\s*[:.]?\s*([^\n]+(?:\n[^\n]+)*)',
            text, re.IGNORECASE
        )
        extracted["experience"] = experience_section.group(1).strip() if experience_section else None
        if not extracted["experience"]:
            missing_fields.append("experience")
        
        # Certifications
        cert_section = re.search(
            r'(?:Certifications|Certifications?|Courses?)\s*[:.]?\s*([^\n]+(?:\n[^\n]+)*)',
            text, re.IGNORECASE
        )
        extracted["certifications"] = cert_section.group(1).strip() if cert_section else None
        
        # Calculate confidence
        filled_fields = sum(1 for v in extracted.values() if v is not None and v != [])
        total_fields = len(extracted)
        confidence = filled_fields / total_fields if total_fields > 0 else 0.0
        
        return {
            "extracted_data": extracted,
            "confidence": confidence,
            "missing_fields": missing_fields,
            "warnings": warnings
        }
    
    def _extract_bank_statement_info(self, text: str, entities: List[Dict]) -> Dict[str, Any]:
        """Extract bank statement-specific fields"""
        extracted = {}
        missing_fields = []
        warnings = []
        
        # Account Number
        account_entity = next((e for e in entities if e["label"] == "Account Number"), None)
        extracted["account_number"] = account_entity["text"] if account_entity else None
        if not extracted["account_number"]:
            # Try alternate pattern
            account_match = re.search(
                r'Account\s*(?:No|Number|#)?\s*[:.]?\s*([\d\s]{8,20})',
                text, re.IGNORECASE
            )
            extracted["account_number"] = account_match.group(1).strip() if account_match else None
        if not extracted["account_number"]:
            missing_fields.append("account_number")
        
        # IFSC Code
        ifsc_entity = next((e for e in entities if e["label"] == "IFSC Code"), None)
        extracted["ifsc"] = ifsc_entity["text"] if ifsc_entity else None
        if not extracted["ifsc"]:
            missing_fields.append("ifsc")
        
        # Transactions (simplified - extract amounts and dates)
        transaction_pattern = r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}).*?([\d,]+\.?\d*)'
        transactions = re.findall(transaction_pattern, text)
        extracted["transactions"] = [
            {"date": t[0], "amount": t[1]} for t in transactions[:10]  # Limit to 10
        ]
        
        # Balance
        balance_match = re.search(
            r'(?:Balance|Closing\s*Balance)\s*[:.]?\s*[\₹$€£]?\s*([\d,]+\.?\d*)',
            text, re.IGNORECASE
        )
        extracted["balance"] = balance_match.group(1) if balance_match else None
        if not extracted["balance"]:
            missing_fields.append("balance")
        
        # Calculate confidence
        filled_fields = sum(1 for v in extracted.values() if v is not None and v != [])
        total_fields = len(extracted)
        confidence = filled_fields / total_fields if total_fields > 0 else 0.0
        
        return {
            "extracted_data": extracted,
            "confidence": confidence,
            "missing_fields": missing_fields,
            "warnings": warnings
        }
    
    def _extract_government_id_info(self, text: str, entities: List[Dict], 
                                    document_type: DocumentType) -> Dict[str, Any]:
        """Extract government ID-specific fields"""
        extracted = {}
        missing_fields = []
        warnings = []
        
        # Name
        name_entity = next((e for e in entities if e["label"] == "Person"), None)
        extracted["name"] = name_entity["text"] if name_entity else None
        if not extracted["name"]:
            missing_fields.append("name")
        
        # Date of Birth
        dob_match = re.search(
            r'(?:DOB|Date\s*of\s*Birth|Birth\s*Date)\s*[:.]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            text, re.IGNORECASE
        )
        extracted["dob"] = dob_match.group(1) if dob_match else None
        if not extracted["dob"]:
            missing_fields.append("dob")
        
        # Address
        address_entity = next((e for e in entities if e["label"] == "Address"), None)
        extracted["address"] = address_entity["text"] if address_entity else None
        if not extracted["address"]:
            # Try to extract address pattern
            address_match = re.search(
                r'(?:Address|Addr)\s*[:.]?\s*([^\n]+(?:\n[^\n]+)*)',
                text, re.IGNORECASE
            )
            extracted["address"] = address_match.group(1).strip() if address_match else None
        if not extracted["address"]:
            missing_fields.append("address")
        
        # Gender
        gender_match = re.search(
            r'(?:Gender|Sex)\s*[:.]?\s*(Male|Female|Other|M|F)',
            text, re.IGNORECASE
        )
        extracted["gender"] = gender_match.group(1) if gender_match else None
        if not extracted["gender"]:
            missing_fields.append("gender")
        
        # ID Number (document-specific)
        if document_type == DocumentType.AADHAAR:
            aadhaar_match = re.search(r'\b\d{4}\s?\d{4}\s?\d{4}\b', text)
            extracted["id_number"] = aadhaar_match.group() if aadhaar_match else None
        elif document_type == DocumentType.PAN_CARD:
            pan_entity = next((e for e in entities if e["label"] == "PAN Number"), None)
            extracted["id_number"] = pan_entity["text"] if pan_entity else None
        elif document_type == DocumentType.DRIVING_LICENSE:
            dl_match = re.search(r'(?:DL|Driving\s*License|Licence)\s*(?:No|Number|#)?\s*[:.]?\s*([\w\d]+)', 
                               text, re.IGNORECASE)
            extracted["id_number"] = dl_match.group(1) if dl_match else None
        elif document_type == DocumentType.PASSPORT:
            passport_match = re.search(r'(?:Passport)\s*(?:No|Number|#)?\s*[:.]?\s*([A-Z]\d{7})', 
                                      text, re.IGNORECASE)
            extracted["id_number"] = passport_match.group(1) if passport_match else None
        
        if not extracted.get("id_number"):
            missing_fields.append("id_number")
        
        # Calculate confidence
        filled_fields = sum(1 for v in extracted.values() if v is not None)
        total_fields = len(extracted)
        confidence = filled_fields / total_fields if total_fields > 0 else 0.0
        
        return {
            "extracted_data": extracted,
            "confidence": confidence,
            "missing_fields": missing_fields,
            "warnings": warnings
        }
    
    def _extract_medical_report_info(self, text: str, entities: List[Dict]) -> Dict[str, Any]:
        """Extract medical report-specific fields"""
        extracted = {}
        missing_fields = []
        warnings = []
        
        # Patient Name
        patient_match = re.search(
            r'(?:Patient|Name)\s*[:.]?\s*([^\n]+)',
            text, re.IGNORECASE
        )
        extracted["patient"] = patient_match.group(1).strip() if patient_match else None
        if not extracted["patient"]:
            missing_fields.append("patient")
        
        # Hospital/Clinic
        hospital_match = re.search(
            r'(?:Hospital|Clinic|Medical\s*Center)\s*[:.]?\s*([^\n]+)',
            text, re.IGNORECASE
        )
        extracted["hospital"] = hospital_match.group(1).strip() if hospital_match else None
        if not extracted["hospital"]:
            missing_fields.append("hospital")
        
        # Doctor
        doctor_match = re.search(
            r'(?:Doctor|Dr|Physician)\s*[:.]?\s*([^\n]+)',
            text, re.IGNORECASE
        )
        extracted["doctor"] = doctor_match.group(1).strip() if doctor_match else None
        
        # Diagnosis
        diagnosis_match = re.search(
            r'(?:Diagnosis|Findings|Result)\s*[:.]?\s*([^\n]+(?:\n[^\n]+)*)',
            text, re.IGNORECASE
        )
        extracted["diagnosis"] = diagnosis_match.group(1).strip() if diagnosis_match else None
        if not extracted["diagnosis"]:
            missing_fields.append("diagnosis")
        
        # Medicines
        medicines_match = re.search(
            r'(?:Medicine|Medication|Drug|Prescription)\s*[:.]?\s*([^\n]+(?:\n[^\n]+)*)',
            text, re.IGNORECASE
        )
        extracted["medicines"] = medicines_match.group(1).strip() if medicines_match else None
        
        # Calculate confidence
        filled_fields = sum(1 for v in extracted.values() if v is not None)
        total_fields = len(extracted)
        confidence = filled_fields / total_fields if total_fields > 0 else 0.0
        
        return {
            "extracted_data": extracted,
            "confidence": confidence,
            "missing_fields": missing_fields,
            "warnings": warnings
        }
    
    def _extract_generic_info(self, text: str, entities: List[Dict]) -> Dict[str, Any]:
        """Extract generic information for unknown document types"""
        extracted = {}
        missing_fields = []
        warnings = ["Generic extraction - document type not specifically supported"]
        
        # Extract basic entities
        for entity in entities:
            label = entity["label"].lower().replace(" ", "_")
            if label not in extracted:
                extracted[label] = entity["text"]
        
        # Extract dates
        dates = re.findall(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}', text)
        if dates:
            extracted["dates"] = dates
        
        # Extract amounts
        amounts = re.findall(r'[\₹$€£]?\s*[\d,]+\.?\d*', text)
        if amounts:
            extracted["amounts"] = amounts
        
        # Calculate confidence
        filled_fields = len(extracted)
        total_fields = 5  # Expected minimum fields
        confidence = min(1.0, filled_fields / total_fields) if total_fields > 0 else 0.0
        
        return {
            "extracted_data": extracted,
            "confidence": confidence,
            "missing_fields": missing_fields,
            "warnings": warnings
        }


# Global information extraction service instance
extraction_service = InformationExtractionService()

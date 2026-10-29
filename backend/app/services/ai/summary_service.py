"""
AI Summary Generation Service
Generates concise summaries describing document purpose, key information, important dates, financial details
"""
import logging
from typing import Dict, List, Any
from app.models.document import DocumentType

logger = logging.getLogger(__name__)


class SummaryService:
    def __init__(self):
        pass
    
    def generate_summary(self, text: str, document_type: DocumentType, 
                         extracted_data: Dict[str, Any], 
                         entities: List[Dict]) -> Dict[str, Any]:
        """
        Generate AI summary of the document
        
        Args:
            text: OCR text
            document_type: Document type
            extracted_data: Extracted key information
            entities: Named entities
            
        Returns:
            Dictionary with summary, purpose, key information, dates, financial details, missing fields, warnings
        """
        try:
            if not text:
                return self._empty_summary()
            
            # Generate summary based on document type
            if document_type == DocumentType.INVOICE:
                return self._generate_invoice_summary(extracted_data, entities)
            elif document_type == DocumentType.RESUME:
                return self._generate_resume_summary(extracted_data, entities)
            elif document_type == DocumentType.BANK_STATEMENT:
                return self._generate_bank_statement_summary(extracted_data, entities)
            elif document_type in [DocumentType.PASSPORT, DocumentType.AADHAAR, 
                                   DocumentType.PAN_CARD, DocumentType.DRIVING_LICENSE]:
                return self._generate_government_id_summary(extracted_data, entities, document_type)
            elif document_type == DocumentType.MEDICAL_REPORT:
                return self._generate_medical_report_summary(extracted_data, entities)
            else:
                return self._generate_generic_summary(text, document_type, extracted_data, entities)
                
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return self._empty_summary()
    
    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary structure"""
        return {
            "summary": "Unable to generate summary.",
            "purpose": "Unknown",
            "key_information": [],
            "important_dates": [],
            "financial_details": None,
            "missing_fields": [],
            "warnings": ["Summary generation failed"]
        }
    
    def _generate_invoice_summary(self, extracted_data: Dict[str, Any], 
                                  entities: List[Dict]) -> Dict[str, Any]:
        """Generate summary for invoice documents"""
        data = extracted_data.get("extracted_data", {})
        missing_fields = extracted_data.get("missing_fields", [])
        warnings = extracted_data.get("warnings", [])
        
        # Build summary
        summary_parts = []
        
        if data.get("seller"):
            summary_parts.append(f"Invoice from {data['seller']}")
        
        if data.get("buyer"):
            summary_parts.append(f"to {data['buyer']}")
        
        if data.get("invoice_number"):
            summary_parts.append(f"Invoice #{data['invoice_number']}")
        
        if data.get("date"):
            summary_parts.append(f"dated {data['date']}")
        
        if data.get("total"):
            summary_parts.append(f"for total amount {data['total']}")
        
        summary = ". ".join(summary_parts) if summary_parts else "Invoice document with incomplete information."
        
        # Purpose
        purpose = "Commercial invoice for goods or services provided"
        
        # Key information
        key_info = []
        if data.get("invoice_number"):
            key_info.append(f"Invoice Number: {data['invoice_number']}")
        if data.get("date"):
            key_info.append(f"Date: {data['date']}")
        if data.get("seller"):
            key_info.append(f"Seller: {data['seller']}")
        if data.get("buyer"):
            key_info.append(f"Buyer: {data['buyer']}")
        if data.get("gst_number"):
            key_info.append(f"GST: {data['gst_number']}")
        
        # Important dates
        important_dates = []
        if data.get("date"):
            important_dates.append(data["date"])
        if data.get("due_date"):
            important_dates.append(f"Due Date: {data['due_date']}")
        
        # Financial details
        financial_details = None
        if data.get("total") or data.get("tax"):
            financial_details = {
                "total": data.get("total"),
                "tax": data.get("tax"),
                "currency": "INR"  # Default
            }
        
        return {
            "summary": summary,
            "purpose": purpose,
            "key_information": key_info,
            "important_dates": important_dates,
            "financial_details": financial_details,
            "missing_fields": missing_fields,
            "warnings": warnings
        }
    
    def _generate_resume_summary(self, extracted_data: Dict[str, Any], 
                                entities: List[Dict]) -> Dict[str, Any]:
        """Generate summary for resume documents"""
        data = extracted_data.get("extracted_data", {})
        missing_fields = extracted_data.get("missing_fields", [])
        warnings = extracted_data.get("warnings", [])
        
        # Build summary
        summary_parts = []
        
        if data.get("name"):
            summary_parts.append(f"Resume of {data['name']}")
        
        if data.get("email"):
            summary_parts.append(f"Contact: {data['email']}")
        
        if data.get("phone"):
            summary_parts.append(f"Phone: {data['phone']}")
        
        skills_count = len(data.get("skills", []))
        if skills_count > 0:
            summary_parts.append(f"listing {skills_count} skills")
        
        summary = ". ".join(summary_parts) if summary_parts else "Resume document with incomplete information."
        
        # Purpose
        purpose = "Professional resume/CV for employment application"
        
        # Key information
        key_info = []
        if data.get("name"):
            key_info.append(f"Name: {data['name']}")
        if data.get("email"):
            key_info.append(f"Email: {data['email']}")
        if data.get("phone"):
            key_info.append(f"Phone: {data['phone']}")
        if data.get("education"):
            key_info.append(f"Education: {data['education'][:100]}...")
        if data.get("experience"):
            key_info.append(f"Experience: {data['experience'][:100]}...")
        
        # Important dates (none typically in resume)
        important_dates = []
        
        # Financial details (none)
        financial_details = None
        
        return {
            "summary": summary,
            "purpose": purpose,
            "key_information": key_info,
            "important_dates": important_dates,
            "financial_details": financial_details,
            "missing_fields": missing_fields,
            "warnings": warnings
        }
    
    def _generate_bank_statement_summary(self, extracted_data: Dict[str, Any], 
                                        entities: List[Dict]) -> Dict[str, Any]:
        """Generate summary for bank statement documents"""
        data = extracted_data.get("extracted_data", {})
        missing_fields = extracted_data.get("missing_fields", [])
        warnings = extracted_data.get("warnings", [])
        
        # Build summary
        summary_parts = []
        
        if data.get("account_number"):
            summary_parts.append(f"Bank statement for account {data['account_number']}")
        
        if data.get("ifsc"):
            summary_parts.append(f"IFSC: {data['ifsc']}")
        
        transactions_count = len(data.get("transactions", []))
        if transactions_count > 0:
            summary_parts.append(f"showing {transactions_count} transactions")
        
        if data.get("balance"):
            summary_parts.append(f"with closing balance {data['balance']}")
        
        summary = ". ".join(summary_parts) if summary_parts else "Bank statement with incomplete information."
        
        # Purpose
        purpose = "Official bank statement showing account transactions and balance"
        
        # Key information
        key_info = []
        if data.get("account_number"):
            key_info.append(f"Account Number: {data['account_number']}")
        if data.get("ifsc"):
            key_info.append(f"IFSC Code: {data['ifsc']}")
        if data.get("balance"):
            key_info.append(f"Balance: {data['balance']}")
        if transactions_count > 0:
            key_info.append(f"Transactions: {transactions_count}")
        
        # Important dates
        important_dates = []
        for tx in data.get("transactions", [])[:3]:
            if tx.get("date"):
                important_dates.append(tx["date"])
        
        # Financial details
        financial_details = {
            "balance": data.get("balance"),
            "transaction_count": transactions_count
        }
        
        return {
            "summary": summary,
            "purpose": purpose,
            "key_information": key_info,
            "important_dates": important_dates,
            "financial_details": financial_details,
            "missing_fields": missing_fields,
            "warnings": warnings
        }
    
    def _generate_government_id_summary(self, extracted_data: Dict[str, Any], 
                                       entities: List[Dict], 
                                       document_type: DocumentType) -> Dict[str, Any]:
        """Generate summary for government ID documents"""
        data = extracted_data.get("extracted_data", {})
        missing_fields = extracted_data.get("missing_fields", [])
        warnings = extracted_data.get("warnings", [])
        
        # Build summary
        summary_parts = []
        
        id_type_names = {
            DocumentType.PASSPORT: "Passport",
            DocumentType.AADHAAR: "Aadhaar Card",
            DocumentType.PAN_CARD: "PAN Card",
            DocumentType.DRIVING_LICENSE: "Driving License"
        }
        
        id_name = id_type_names.get(document_type, "Government ID")
        
        if data.get("name"):
            summary_parts.append(f"{id_name} issued to {data['name']}")
        
        if data.get("id_number"):
            summary_parts.append(f"ID Number: {data['id_number']}")
        
        if data.get("dob"):
            summary_parts.append(f"Date of Birth: {data['dob']}")
        
        summary = ". ".join(summary_parts) if summary_parts else f"{id_name} with incomplete information."
        
        # Purpose
        purpose = f"Official {id_name.lower()} for identity verification"
        
        # Key information
        key_info = []
        if data.get("name"):
            key_info.append(f"Name: {data['name']}")
        if data.get("id_number"):
            key_info.append(f"ID Number: {data['id_number']}")
        if data.get("dob"):
            key_info.append(f"Date of Birth: {data['dob']}")
        if data.get("gender"):
            key_info.append(f"Gender: {data['gender']}")
        if data.get("address"):
            key_info.append(f"Address: {data['address'][:100]}...")
        
        # Important dates
        important_dates = []
        if data.get("dob"):
            important_dates.append(f"DOB: {data['dob']}")
        
        # Financial details (none)
        financial_details = None
        
        return {
            "summary": summary,
            "purpose": purpose,
            "key_information": key_info,
            "important_dates": important_dates,
            "financial_details": financial_details,
            "missing_fields": missing_fields,
            "warnings": warnings
        }
    
    def _generate_medical_report_summary(self, extracted_data: Dict[str, Any], 
                                        entities: List[Dict]) -> Dict[str, Any]:
        """Generate summary for medical report documents"""
        data = extracted_data.get("extracted_data", {})
        missing_fields = extracted_data.get("missing_fields", [])
        warnings = extracted_data.get("warnings", [])
        
        # Build summary
        summary_parts = []
        
        if data.get("patient"):
            summary_parts.append(f"Medical report for patient {data['patient']}")
        
        if data.get("hospital"):
            summary_parts.append(f"from {data['hospital']}")
        
        if data.get("doctor"):
            summary_parts.append(f"Dr. {data['doctor']}")
        
        if data.get("diagnosis"):
            summary_parts.append(f"Diagnosis: {data['diagnosis'][:100]}...")
        
        summary = ". ".join(summary_parts) if summary_parts else "Medical report with incomplete information."
        
        # Purpose
        purpose = "Medical report documenting patient diagnosis and treatment"
        
        # Key information
        key_info = []
        if data.get("patient"):
            key_info.append(f"Patient: {data['patient']}")
        if data.get("hospital"):
            key_info.append(f"Hospital: {data['hospital']}")
        if data.get("doctor"):
            key_info.append(f"Doctor: {data['doctor']}")
        if data.get("diagnosis"):
            key_info.append(f"Diagnosis: {data['diagnosis']}")
        if data.get("medicines"):
            key_info.append(f"Medicines: {data['medicines'][:100]}...")
        
        # Important dates (none typically)
        important_dates = []
        
        # Financial details (none)
        financial_details = None
        
        return {
            "summary": summary,
            "purpose": purpose,
            "key_information": key_info,
            "important_dates": important_dates,
            "financial_details": financial_details,
            "missing_fields": missing_fields,
            "warnings": warnings
        }
    
    def _generate_generic_summary(self, text: str, document_type: DocumentType, 
                                 extracted_data: Dict[str, Any], 
                                 entities: List[Dict]) -> Dict[str, Any]:
        """Generate summary for generic/unknown document types"""
        data = extracted_data.get("extracted_data", {})
        missing_fields = extracted_data.get("missing_fields", [])
        warnings = extracted_data.get("warnings", [])
        
        # Build summary
        word_count = len(text.split())
        char_count = len(text)
        
        summary = f"Document of type '{document_type.value}' containing {word_count} words ({char_count} characters). "
        
        # Add entity information
        entity_types = set(e["label"] for e in entities)
        if entity_types:
            summary += f"Detected entities: {', '.join(entity_types)}."
        
        # Purpose
        purpose = f"Document classified as {document_type.value}"
        
        # Key information
        key_info = []
        for key, value in data.items():
            if value and isinstance(value, str):
                key_info.append(f"{key.replace('_', ' ').title()}: {value[:100]}")
        
        # Important dates
        important_dates = data.get("dates", [])
        
        # Financial details
        financial_details = None
        if data.get("amounts"):
            financial_details = {
                "amounts": data["amounts"][:5]
            }
        
        return {
            "summary": summary,
            "purpose": purpose,
            "key_information": key_info[:10],  # Limit to 10 items
            "important_dates": important_dates[:5],  # Limit to 5 dates
            "financial_details": financial_details,
            "missing_fields": missing_fields,
            "warnings": warnings
        }


# Global summary service instance
summary_service = SummaryService()

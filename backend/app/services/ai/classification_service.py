"""
Document Classification Service using LayoutLMv3
Classifies documents into 15+ categories with confidence scores
"""
import logging
import torch
from transformers import AutoProcessor, AutoModelForSequenceClassification
from typing import Dict, List, Any
from app.core.config import settings
from app.models.document import DocumentType

logger = logging.getLogger(__name__)


class DocumentClassificationService:
    def __init__(self):
        self.model = None
        self.processor = None
        self.label_map = {
            0: DocumentType.INVOICE,
            1: DocumentType.RECEIPT,
            2: DocumentType.RESUME,
            3: DocumentType.PASSPORT,
            4: DocumentType.AADHAAR,
            5: DocumentType.PAN_CARD,
            6: DocumentType.DRIVING_LICENSE,
            7: DocumentType.BANK_STATEMENT,
            8: DocumentType.MEDICAL_REPORT,
            9: DocumentType.CERTIFICATE,
            10: DocumentType.RESEARCH_PAPER,
            11: DocumentType.UTILITY_BILL,
            12: DocumentType.CONTRACT,
            13: DocumentType.INSURANCE,
            14: DocumentType.TAX_DOCUMENT,
            15: DocumentType.OTHER,
        }
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize LayoutLMv3 model for document classification"""
        try:
            model_name = settings.CLASSIFICATION_MODEL
            
            logger.info(f"Loading classification model: {model_name}")
            
            self.processor = AutoProcessor.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            
            # Move to GPU if available
            if settings.DEVICE == "cuda" and torch.cuda.is_available():
                self.model = self.model.to("cuda")
                logger.info("Model moved to GPU")
            
            self.model.eval()
            logger.info("Document classification model initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize classification model: {e}")
            # Fallback to rule-based classification
            self.model = None
    
    def classify(self, text: str, image_path: str = None) -> Dict[str, Any]:
        """
        Classify document based on text and optional image
        
        Args:
            text: Extracted text from OCR
            image_path: Path to document image (optional)
            
        Returns:
            Dictionary with document type, confidence, and probabilities
        """
        if self.model is None:
            return self._rule_based_classification(text)
        
        try:
            # Process text
            inputs = self.processor(
                text=text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )
            
            # Move to GPU if available
            if settings.DEVICE == "cuda" and torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probabilities = torch.softmax(logits, dim=-1)
            
            # Get top prediction
            predicted_class_id = torch.argmax(probabilities, dim=-1).item()
            confidence = probabilities[0][predicted_class_id].item()
            
            # Convert to document type
            document_type = self.label_map.get(predicted_class_id, DocumentType.OTHER)
            
            # Get all probabilities
            all_probabilities = {
                self.label_map.get(i, DocumentType.OTHER).value: probabilities[0][i].item()
                for i in range(len(self.label_map))
            }
            
            return {
                "document_type": document_type,
                "confidence": confidence,
                "probabilities": all_probabilities
            }
            
        except Exception as e:
            logger.error(f"Model-based classification failed: {e}")
            return self._rule_based_classification(text)
    
    def _rule_based_classification(self, text: str) -> Dict[str, Any]:
        """
        Fallback rule-based classification using keyword matching
        """
        text_lower = text.lower()
        
        # Define keyword patterns for each document type
        keywords = {
            DocumentType.INVOICE: ["invoice", "bill", "tax invoice", "gst invoice"],
            DocumentType.RECEIPT: ["receipt", "received", "payment received"],
            DocumentType.RESUME: ["resume", "cv", "curriculum vitae", "experience", "education"],
            DocumentType.PASSPORT: ["passport", "república", "passport no"],
            DocumentType.AADHAAR: ["aadhaar", "uidai", "unique identification"],
            DocumentType.PAN_CARD: ["pan card", "permanent account number", "income tax"],
            DocumentType.DRIVING_LICENSE: ["driving license", "driver licence", "dl no"],
            DocumentType.BANK_STATEMENT: ["bank statement", "account statement", "transaction"],
            DocumentType.MEDICAL_REPORT: ["medical report", "diagnosis", "prescription", "hospital"],
            DocumentType.CERTIFICATE: ["certificate", "certified", "certification"],
            DocumentType.RESEARCH_PAPER: ["abstract", "introduction", "methodology", "references"],
            DocumentType.UTILITY_BILL: ["electricity bill", "water bill", "utility", "consumption"],
            DocumentType.CONTRACT: ["contract", "agreement", "terms and conditions"],
            DocumentType.INSURANCE: ["insurance", "policy", "coverage", "premium"],
            DocumentType.TAX_DOCUMENT: ["tax return", "income tax", "tax assessment", "form"],
        }
        
        # Score each document type
        scores = {}
        for doc_type, patterns in keywords.items():
            score = sum(1 for pattern in patterns if pattern in text_lower)
            scores[doc_type] = score
        
        # Get document type with highest score
        if not scores or max(scores.values()) == 0:
            document_type = DocumentType.OTHER
            confidence = 0.3
        else:
            document_type = max(scores, key=scores.get)
            max_score = scores[document_type]
            confidence = min(0.9, 0.4 + (max_score * 0.1))
        
        # Generate probabilities based on scores
        total_score = sum(scores.values()) + 1  # +1 for OTHER
        probabilities = {
            doc_type.value: (score + 1) / total_score
            for doc_type, score in scores.items()
        }
        probabilities[DocumentType.OTHER.value] = 1 / total_score
        
        return {
            "document_type": document_type,
            "confidence": confidence,
            "probabilities": probabilities
        }


# Global classification service instance
classification_service = DocumentClassificationService()

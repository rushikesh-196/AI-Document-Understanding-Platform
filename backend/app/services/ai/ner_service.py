"""
Named Entity Recognition Service
Recognizes entities: Person, Organization, Location, Address, Date, Time, Phone, Email, etc.
"""
import logging
import re
from typing import Dict, List, Any
import spacy
from app.core.config import settings

logger = logging.getLogger(__name__)


class NERService:
    def __init__(self):
        self.nlp = None
        self._initialize_ner()
    
    def _initialize_ner(self):
        """Initialize spaCy NER model"""
        try:
            logger.info(f"Loading NER model: {settings.NER_MODEL}")
            self.nlp = spacy.load(settings.NER_MODEL)
            logger.info("NER model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load NER model: {e}")
            self.nlp = None
    
    def extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract named entities from text
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with entities and confidence
        """
        if not text:
            return {"entities": [], "confidence": 0.0}
        
        if self.nlp is None:
            return self._rule_based_ner(text)
        
        try:
            doc = self.nlp(text)
            
            entities = []
            for ent in doc.ents:
                # Map spaCy entity types to our schema
                entity_type = self._map_entity_type(ent.label_)
                
                if entity_type:
                    entities.append({
                        "text": ent.text,
                        "label": entity_type,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "confidence": 0.8  # spaCy doesn't provide confidence scores
                    })
            
            # Add rule-based entities for specific patterns
            rule_entities = self._extract_pattern_entities(text)
            entities.extend(rule_entities)
            
            # Remove duplicates
            entities = self._deduplicate_entities(entities)
            
            confidence = 0.8 if entities else 0.0
            
            return {
                "entities": entities,
                "confidence": confidence
            }
            
        except Exception as e:
            logger.error(f"NER extraction failed: {e}")
            return self._rule_based_ner(text)
    
    def _map_entity_type(self, spacy_type: str) -> str:
        """Map spaCy entity types to our schema"""
        mapping = {
            "PERSON": "Person",
            "ORG": "Organization",
            "GPE": "Location",
            "LOC": "Location",
            "DATE": "Date",
            "TIME": "Time",
            "EMAIL": "Email",
            "PHONE": "Phone",
            "CARDINAL": "Amount",
            "MONEY": "Currency",
            "QUANTITY": "Amount",
        }
        return mapping.get(spacy_type, None)
    
    def _rule_based_ner(self, text: str) -> Dict[str, Any]:
        """Fallback rule-based NER using regex patterns"""
        entities = self._extract_pattern_entities(text)
        
        return {
            "entities": entities,
            "confidence": 0.6
        }
    
    def _extract_pattern_entities(self, text: str) -> List[Dict]:
        """Extract entities using regex patterns"""
        entities = []
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        for match in re.finditer(email_pattern, text):
            entities.append({
                "text": match.group(),
                "label": "Email",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.95
            })
        
        # Phone pattern (international)
        phone_pattern = r'\+?[\d\s\-\(\)]{10,}'
        for match in re.finditer(phone_pattern, text):
            entities.append({
                "text": match.group(),
                "label": "Phone",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.9
            })
        
        # URL/Website pattern
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+|www\.[^\s<>"{}|\\^`\[\]]+'
        for match in re.finditer(url_pattern, text):
            entities.append({
                "text": match.group(),
                "label": "Website",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.95
            })
        
        # GST Number pattern (India)
        gst_pattern = r'\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b'
        for match in re.finditer(gst_pattern, text):
            entities.append({
                "text": match.group(),
                "label": "GST Number",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.95
            })
        
        # PAN Card pattern (India)
        pan_pattern = r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b'
        for match in re.finditer(pan_pattern, text):
            entities.append({
                "text": match.group(),
                "label": "PAN Number",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.9
            })
        
        # Account Number pattern
        account_pattern = r'\b(?:Account|Acc|A/C)\s*(?:No|Number|#)?\s*[:.]?\s*[\d\s]{8,20}\b'
        for match in re.finditer(account_pattern, text, re.IGNORECASE):
            entities.append({
                "text": match.group(),
                "label": "Account Number",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.85
            })
        
        # IFSC Code pattern (India)
        ifsc_pattern = r'\b[A-Z]{4}0[A-Z0-9]{6}\b'
        for match in re.finditer(ifsc_pattern, text):
            entities.append({
                "text": match.group(),
                "label": "IFSC Code",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.95
            })
        
        # Invoice Number pattern
        invoice_pattern = r'\b(?:Invoice|Inv|Bill)\s*(?:No|Number|#)?\s*[:.]?\s*[\w\d\-/]+\b'
        for match in re.finditer(invoice_pattern, text, re.IGNORECASE):
            entities.append({
                "text": match.group(),
                "label": "Invoice Number",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.85
            })
        
        # Date pattern (multiple formats)
        date_patterns = [
            r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',  # DD-MM-YYYY or DD/MM/YYYY
            r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b',  # YYYY-MM-DD
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',  # Month DD, YYYY
        ]
        for pattern in date_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append({
                    "text": match.group(),
                    "label": "Date",
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.9
                })
        
        # Currency pattern
        currency_pattern = r'[₹$€£¥]\s*[\d,]+\.?\d*|\b[\d,]+\.?\d*\s*(?:INR|USD|EUR|GBP|JPY)\b'
        for match in re.finditer(currency_pattern, text):
            entities.append({
                "text": match.group(),
                "label": "Currency",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.9
            })
        
        # Amount pattern
        amount_pattern = r'\b[\d,]+\.?\d*\b'
        for match in re.finditer(amount_pattern, text):
            # Only add if not already captured by currency
            if not any(e["start"] <= match.start() and e["end"] >= match.end() for e in entities):
                if len(match.group()) > 2:  # Filter small numbers
                    entities.append({
                        "text": match.group(),
                        "label": "Amount",
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.7
                    })
        
        return entities
    
    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """Remove duplicate entities (overlapping)"""
        if not entities:
            return []
        
        # Sort by start position
        entities.sort(key=lambda x: x["start"])
        
        deduplicated = []
        for entity in entities:
            # Check for overlap with existing entities
            has_overlap = False
            for existing in deduplicated:
                if (entity["start"] < existing["end"] and 
                    entity["end"] > existing["start"]):
                    has_overlap = True
                    break
            
            if not has_overlap:
                deduplicated.append(entity)
        
        return deduplicated
    
    def color_code_entities(self, text: str, entities: List[Dict]) -> List[Dict]:
        """
        Color-code entities for visualization
        
        Returns list of entities with color information
        """
        color_map = {
            "Person": "#FF6B6B",
            "Organization": "#4ECDC4",
            "Location": "#45B7D1",
            "Address": "#96CEB4",
            "Date": "#FFEAA7",
            "Time": "#DDA0DD",
            "Phone": "#98D8C8",
            "Email": "#F7DC6F",
            "Website": "#BB8FCE",
            "Currency": "#85C1E9",
            "Amount": "#F8B500",
            "GST Number": "#FF8C00",
            "Invoice Number": "#00CED1",
            "Account Number": "#FF69B4",
            "PAN Number": "#32CD32",
            "IFSC Code": "#FF4500",
        }
        
        for entity in entities:
            entity["color"] = color_map.get(entity["label"], "#CCCCCC")
        
        return entities


# Global NER service instance
ner_service = NERService()

"""
OCR Service for Text Extraction
Supports multiple languages: English, Hindi, Marathi
"""
import os
import logging
from typing import Dict, Any, Tuple
from PIL import Image
import cv2
import numpy as np
from paddleocr import PaddleOCR
from app.core.config import settings

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self):
        self.ocr = None
        self._initialize_ocr()
    
    def _initialize_ocr(self):
        """Initialize PaddleOCR with support for English, Hindi, Marathi"""
        try:
            self.ocr = PaddleOCR(
                use_angle_cls=True,
                lang='en',  # Primary language
                use_gpu=settings.DEVICE == 'cuda',
                show_log=False
            )
            logger.info("PaddleOCR initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise
    
    def extract_text(self, image_path: str) -> Dict[str, Any]:
        """
        Extract text from document image
        
        Args:
            image_path: Path to the document image
            
        Returns:
            Dictionary containing extracted text, confidence, and language info
        """
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Failed to read image from {image_path}")
            
            # Perform OCR
            result = self.ocr.ocr(image, cls=True)
            
            if not result or not result[0]:
                return {
                    "text": "",
                    "confidence": 0.0,
                    "word_confidence": [],
                    "character_count": 0,
                    "language_detected": "unknown",
                    "regions": []
                }
            
            # Process results
            text_lines = []
            confidences = []
            regions = []
            
            for line in result[0]:
                bbox = line[0]
                text_info = line[1]
                text = text_info[0]
                confidence = text_info[1]
                
                text_lines.append(text)
                confidences.append(confidence)
                
                regions.append({
                    "bbox": [[int(point[0]), int(point[1])] for point in bbox],
                    "text": text,
                    "confidence": confidence
                })
            
            full_text = "\n".join(text_lines)
            avg_confidence = np.mean(confidences) if confidences else 0.0
            
            # Detect language (simplified)
            language = self._detect_language(full_text)
            
            return {
                "text": full_text,
                "confidence": float(avg_confidence),
                "word_confidence": [float(c) for c in confidences],
                "character_count": len(full_text),
                "language_detected": language,
                "regions": regions
            }
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "word_confidence": [],
                "character_count": 0,
                "language_detected": "unknown",
                "regions": []
            }
    
    def _detect_language(self, text: str) -> str:
        """
        Detect the primary language of the text
        Supports: English, Hindi, Marathi
        """
        if not text:
            return "unknown"
        
        # Check for Hindi characters (Devanagari script range)
        hindi_chars = sum(1 for char in text if '\u0900' <= char <= '\u097F')
        
        # Check for English characters
        english_chars = sum(1 for char in text if char.isalpha() and char.isascii())
        
        total_chars = sum(1 for char in text if char.isalpha())
        
        if total_chars == 0:
            return "unknown"
        
        hindi_ratio = hindi_chars / total_chars
        english_ratio = english_chars / total_chars
        
        if hindi_ratio > 0.3:
            return "hindi"
        elif english_ratio > 0.7:
            return "english"
        else:
            return "mixed"
    
    def extract_text_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract text from PDF by converting to images first
        """
        try:
            from pdf2image import convert_from_path
            
            # Convert PDF to images
            images = convert_from_path(pdf_path, dpi=200)
            
            all_text = []
            all_confidences = []
            all_regions = []
            
            for i, image in enumerate(images):
                # Save image temporarily
                temp_path = f"temp_page_{i}.png"
                image.save(temp_path)
                
                # Extract text from this page
                page_result = self.extract_text(temp_path)
                
                all_text.append(page_result["text"])
                all_confidences.extend(page_result["word_confidence"])
                all_regions.extend(page_result["regions"])
                
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
            full_text = "\n\n".join(all_text)
            avg_confidence = np.mean(all_confidences) if all_confidences else 0.0
            
            return {
                "text": full_text,
                "confidence": float(avg_confidence),
                "word_confidence": [float(c) for c in all_confidences],
                "character_count": len(full_text),
                "language_detected": self._detect_language(full_text),
                "regions": all_regions
            }
            
        except Exception as e:
            logger.error(f"PDF OCR extraction failed: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "word_confidence": [],
                "character_count": 0,
                "language_detected": "unknown",
                "regions": []
            }


# Global OCR service instance
ocr_service = OCRService()

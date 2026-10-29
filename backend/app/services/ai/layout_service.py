"""
Layout Analysis Service
Detects and visualizes document layout elements: headers, footers, tables, images, etc.
"""
import logging
import cv2
import numpy as np
from typing import Dict, List, Any, Tuple
from PIL import Image

logger = logging.getLogger(__name__)


class LayoutAnalysisService:
    def __init__(self):
        pass
    
    def analyze_layout(self, image_path: str, ocr_regions: List[Dict]) -> Dict[str, Any]:
        """
        Analyze document layout using computer vision and OCR regions
        
        Args:
            image_path: Path to document image
            ocr_regions: OCR text regions with bounding boxes
            
        Returns:
            Dictionary containing detected layout elements
        """
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Failed to read image from {image_path}")
            
            height, width = image.shape[:2]
            
            # Detect various layout elements
            headers = self._detect_headers(image, ocr_regions, height, width)
            footers = self._detect_footers(image, ocr_regions, height, width)
            paragraphs = self._detect_paragraphs(ocr_regions)
            tables = self._detect_tables(image)
            images = self._detect_images(image)
            logos = self._detect_logos(image)
            signatures = self._detect_signatures(image)
            qr_codes = self._detect_qr_codes(image)
            stamps = self._detect_stamps(image)
            forms = self._detect_forms(image, ocr_regions)
            text_blocks = self._detect_text_blocks(ocr_regions)
            
            return {
                "headers": headers,
                "footers": footers,
                "paragraphs": paragraphs,
                "tables": tables,
                "images": images,
                "logos": logos,
                "signatures": signatures,
                "qr_codes": qr_codes,
                "stamps": stamps,
                "forms": forms,
                "text_blocks": text_blocks
            }
            
        except Exception as e:
            logger.error(f"Layout analysis failed: {e}")
            return {
                "headers": [],
                "footers": [],
                "paragraphs": [],
                "tables": [],
                "images": [],
                "logos": [],
                "signatures": [],
                "qr_codes": [],
                "stamps": [],
                "forms": [],
                "text_blocks": []
            }
    
    def _detect_headers(self, image: np.ndarray, ocr_regions: List[Dict], 
                        height: int, width: int) -> List[Dict]:
        """Detect headers in the top portion of the document"""
        headers = []
        header_region_threshold = height * 0.15  # Top 15%
        
        for region in ocr_regions:
            bbox = region["bbox"]
            # Calculate average Y position
            avg_y = sum(point[1] for point in bbox) / len(bbox)
            
            if avg_y < header_region_threshold:
                # Check if it looks like a header (larger font, bold)
                text = region["text"]
                if len(text) < 100 and text.strip():  # Headers are usually short
                    headers.append({
                        "bbox": bbox,
                        "text": text,
                        "confidence": region["confidence"]
                    })
        
        return headers
    
    def _detect_footers(self, image: np.ndarray, ocr_regions: List[Dict],
                       height: int, width: int) -> List[Dict]:
        """Detect footers in the bottom portion of the document"""
        footers = []
        footer_region_threshold = height * 0.85  # Bottom 15%
        
        for region in ocr_regions:
            bbox = region["bbox"]
            avg_y = sum(point[1] for point in bbox) / len(bbox)
            
            if avg_y > footer_region_threshold:
                text = region["text"]
                if len(text) < 100 and text.strip():
                    footers.append({
                        "bbox": bbox,
                        "text": text,
                        "confidence": region["confidence"]
                    })
        
        return footers
    
    def _detect_paragraphs(self, ocr_regions: List[Dict]) -> List[Dict]:
        """Group text regions into paragraphs based on proximity"""
        if not ocr_regions:
            return []
        
        paragraphs = []
        current_paragraph = []
        last_y = None
        
        # Sort regions by Y position
        sorted_regions = sorted(ocr_regions, key=lambda r: r["bbox"][0][1])
        
        for region in sorted_regions:
            bbox = region["bbox"]
            current_y = bbox[0][1]
            
            if last_y is None:
                current_paragraph.append(region)
            elif current_y - last_y < 30:  # Threshold for same paragraph
                current_paragraph.append(region)
            else:
                # Save current paragraph
                if current_paragraph:
                    paragraphs.append(self._merge_regions(current_paragraph))
                current_paragraph = [region]
            
            last_y = current_y
        
        # Don't forget the last paragraph
        if current_paragraph:
            paragraphs.append(self._merge_regions(current_paragraph))
        
        return paragraphs
    
    def _merge_regions(self, regions: List[Dict]) -> Dict:
        """Merge adjacent text regions into a single paragraph"""
        if not regions:
            return {}
        
        # Calculate combined bounding box
        all_x = [point[0] for region in regions for point in region["bbox"]]
        all_y = [point[1] for region in regions for point in region["bbox"]]
        
        combined_bbox = [
            [min(all_x), min(all_y)],
            [max(all_x), min(all_y)],
            [max(all_x), max(all_y)],
            [min(all_x), max(all_y)]
        ]
        
        # Combine text
        combined_text = " ".join(region["text"] for region in regions)
        
        # Average confidence
        avg_confidence = sum(region["confidence"] for region in regions) / len(regions)
        
        return {
            "bbox": combined_bbox,
            "text": combined_text,
            "confidence": avg_confidence
        }
    
    def _detect_tables(self, image: np.ndarray) -> List[Dict]:
        """Detect table structures using horizontal and vertical lines"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect horizontal lines
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        horizontal_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel)
        
        # Detect vertical lines
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        vertical_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, vertical_kernel)
        
        # Combine lines
        table_mask = cv2.add(horizontal_lines, vertical_lines)
        
        # Find contours
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        tables = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter small regions
            if w > 100 and h > 50:
                tables.append({
                    "bbox": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                    "confidence": 0.7,
                    "rows": int(h / 30),  # Estimate
                    "columns": int(w / 50)  # Estimate
                })
        
        return tables
    
    def _detect_images(self, image: np.ndarray) -> List[Dict]:
        """Detect images and graphics in the document"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply edge detection
        edges = cv2.Canny(gray, 50, 150)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detected_images = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter regions that might be images
            area = w * h
            if area > 10000 and w > 50 and h > 50:
                detected_images.append({
                    "bbox": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                    "confidence": 0.6
                })
        
        return detected_images
    
    def _detect_logos(self, image: np.ndarray) -> List[Dict]:
        """Detect logos (typically small graphics in corners)"""
        height, width = image.shape[:2]
        
        # Define corner regions
        top_left = (0, 0, width // 4, height // 4)
        top_right = (3 * width // 4, 0, width, height // 4)
        
        corners = [top_left, top_right]
        logos = []
        
        for x, y, x2, y2 in corners:
            corner_region = image[y:y2, x:x2]
            
            # Detect edges in corner
            gray = cv2.cvtColor(corner_region, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            # Count edge pixels
            edge_count = np.sum(edges > 0)
            region_area = (x2 - x) * (y2 - y)
            
            # If high edge density, might be a logo
            if edge_count / region_area > 0.1:
                logos.append({
                    "bbox": [[x, y], [x2, y], [x2, y2], [x, y2]],
                    "confidence": 0.5
                })
        
        return logos
    
    def _detect_signatures(self, image: np.ndarray) -> List[Dict]:
        """Detect signature regions"""
        # Signatures are typically horizontal lines with some variation
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Define horizontal kernel
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
        
        # Detect horizontal lines
        horizontal_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel)
        
        # Find contours
        contours, _ = cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        signatures = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Signature characteristics
            aspect_ratio = w / h if h > 0 else 0
            if 3 < aspect_ratio < 10 and w > 50:
                signatures.append({
                    "bbox": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                    "confidence": 0.6
                })
        
        return signatures
    
    def _detect_qr_codes(self, image: np.ndarray) -> List[Dict]:
        """Detect QR codes"""
        # Initialize QR code detector
        detector = cv2.QRCodeDetector()
        
        # Detect and decode
        data, bbox, _ = detector.detectAndDecode(image)
        
        qr_codes = []
        if bbox is not None:
            bbox = bbox[0].astype(int)
            qr_codes.append({
                "bbox": [[int(point[0]), int(point[1])] for point in bbox],
                "data": data if data else "",
                "confidence": 0.9
            })
        
        return qr_codes
    
    def _detect_stamps(self, image: np.ndarray) -> List[Dict]:
        """Detect circular or oval stamps"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect circles using Hough transform
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=50,
            param1=50,
            param2=30,
            minRadius=20,
            maxRadius=100
        )
        
        stamps = []
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                stamps.append({
                    "bbox": [[x - r, y - r], [x + r, y - r], [x + r, y + r], [x - r, y + r]],
                    "confidence": 0.7,
                    "radius": r
                })
        
        return stamps
    
    def _detect_forms(self, image: np.ndarray, ocr_regions: List[Dict]) -> List[Dict]:
        """Detect form fields and checkboxes"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect checkboxes (small squares)
        checkbox_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        checkboxes = cv2.morphologyEx(gray, cv2.MORPH_OPEN, checkbox_kernel)
        
        # Find contours
        contours, _ = cv2.findContours(checkboxes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        forms = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Checkbox characteristics
            aspect_ratio = w / h if h > 0 else 0
            if 0.8 < aspect_ratio < 1.2 and 10 < w < 50:
                forms.append({
                    "bbox": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                    "type": "checkbox",
                    "confidence": 0.6
                })
        
        return forms
    
    def _detect_text_blocks(self, ocr_regions: List[Dict]) -> List[Dict]:
        """Return all text regions as blocks"""
        return [
            {
                "bbox": region["bbox"],
                "text": region["text"],
                "confidence": region["confidence"]
            }
            for region in ocr_regions
        ]
    
    def reconstruct_formatted_text(self, ocr_regions: List[Dict], 
                                   document_type: str = "generic") -> str:
        """
        Reconstruct formatted text from OCR regions with proper layout structure.
        
        Args:
            ocr_regions: OCR text regions with bounding boxes
            document_type: Type of document (invoice, receipt, generic, etc.)
            
        Returns:
            Formatted text string with proper structure and alignment
        """
        if not ocr_regions:
            return ""
        
        # Sort regions by Y position (top to bottom), then by X position (left to right)
        sorted_regions = sorted(ocr_regions, key=lambda r: (r["bbox"][0][1], r["bbox"][0][0]))
        
        # Group regions into lines based on Y proximity
        lines = self._group_regions_by_line(sorted_regions)
        
        # Format based on document type
        if document_type.lower() in ["invoice", "receipt"]:
            return self._format_invoice_text(lines)
        else:
            return self._format_generic_text(lines)
    
    def _group_regions_by_line(self, regions: List[Dict], 
                              y_threshold: int = 20) -> List[List[Dict]]:
        """Group OCR regions into lines based on Y coordinate proximity"""
        if not regions:
            return []
        
        lines = []
        current_line = [regions[0]]
        current_y = regions[0]["bbox"][0][1]
        
        for region in regions[1:]:
            region_y = region["bbox"][0][1]
            if abs(region_y - current_y) <= y_threshold:
                current_line.append(region)
            else:
                # Sort current line by X position
                current_line.sort(key=lambda r: r["bbox"][0][0])
                lines.append(current_line)
                current_line = [region]
                current_y = region_y
        
        # Don't forget the last line
        if current_line:
            current_line.sort(key=lambda r: r["bbox"][0][0])
            lines.append(current_line)
        
        return lines
    
    def _format_invoice_text(self, lines: List[List[Dict]]) -> str:
        """Format invoice/receipt text with proper table structure"""
        formatted_lines = []
        
        for line_regions in lines:
            # Join text in the line
            line_text = " ".join(r["text"] for r in line_regions)
            
            # Detect section headers
            if any(kw in line_text.lower() for kw in 
                   ["description", "item", "qty", "quantity", "price", "total", "amount"]):
                formatted_lines.append("\n" + line_text.upper())
            elif any(kw in line_text.lower() for kw in 
                     ["total", "subtotal", "tax", "due", "balance"]):
                formatted_lines.append("\n" + line_text)
            elif any(kw in line_text.lower() for kw in 
                     ["bill to", "ship to", "invoice", "date", "payment"]):
                formatted_lines.append(line_text)
            else:
                formatted_lines.append(line_text)
        
        return "\n".join(formatted_lines)
    
    def _format_generic_text(self, lines: List[List[Dict]]) -> str:
        """Format generic document text with paragraph structure"""
        formatted_lines = []
        
        for line_regions in lines:
            line_text = " ".join(r["text"] for r in line_regions)
            
            # Detect headings (short, uppercase, or ending with colon)
            is_heading = (
                (line_text.isupper() and len(line_text) < 60) or
                line_text.endswith(":") or
                any(line_text.lower().startswith(kw) for kw in 
                    ["section", "chapter", "part", "summary"])
            )
            
            if is_heading and formatted_lines:
                formatted_lines.append("")  # Add blank line before heading
                formatted_lines.append(line_text)
            else:
                formatted_lines.append(line_text)
        
        return "\n".join(formatted_lines)


# Global layout analysis service instance
layout_service = LayoutAnalysisService()

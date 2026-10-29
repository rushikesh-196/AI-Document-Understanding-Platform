# AI Document Understanding Platform (Intelligent OCR)

## Project Overview

The AI Document Understanding Platform is a complete intelligent OCR system that extracts structured information from scanned documents, images, and PDFs. The platform combines OCR, image preprocessing, NLP, and pattern-based extraction to surface key fields and entities in a clean, exportable format.

The system is designed to support a modern user workflow: upload documents, perform text extraction, identify important data fields, review results in a dashboard, and export the extracted output.

---

## Functional Requirements

The platform must support the following functionality:

| Functional Requirement | Description |
|---|---|
| User Registration | Create a secure user account. |
| User Login | Authenticate users before granting access. |
| Upload Document | Upload PDF, JPG, and PNG documents for processing. |
| OCR Processing | Extract text content from uploaded documents. |
| AI Extraction | Detect and extract important fields such as names, dates, invoice numbers, totals, phone numbers, emails, and GST numbers. |
| Search | Search previously processed documents and extracted metadata. |
| Export | Download processed results as JSON and CSV. |
| Dashboard | View statistics, document history, and extraction summaries. |

---

## Problem Statement

Manual data entry and document processing remain slow and error-prone for businesses that receive invoices, receipts, identity documents, and reports in unstructured form. Existing systems often fail to produce accurate structured data, especially when document quality varies or formats differ.

This platform addresses these issues by automating text extraction, field identification, and entity recognition while making results easy to review and export.

---

## Objectives

- Build a complete OCR-based document understanding system.
- Extract structured business fields automatically from documents.
- Recognize named entities such as organizations, people, dates, emails, and amounts.
- Provide a dashboard for review and history tracking.
- Support export of extraction results in JSON and CSV.
- Maintain secure user access and upload history.

---

## System Architecture

### High-Level Architecture

```text
User Browser
    │
    ▼
Frontend UI (HTML/CSS/JS)
    │
    ▼
Backend API (Flask/Python)
    │
    ▼
OCR + NLP Pipeline
    ├─ Image Preprocessing (OpenCV)
    ├─ OCR Extraction (PaddleOCR, PyMuPDF fallback)
    ├─ Entity Recognition (spaCy)
    ├─ Regex Field Extraction
    └─ JSON/CSV Export
    │
    ▼
MySQL Database (Users, Upload History, Metadata)
```

### Workflow Diagram

```text
User Login
    ↓
Upload Document
    ↓
OpenCV Preprocessing
    ↓
PaddleOCR Text Extraction
    ↓
Entity Detection (spaCy)
    ↓
Regex Field Extraction
    ↓
Display Results in Dashboard
    ↓
Export JSON / CSV
```

---

## Technology Stack

### Frontend

- **HTML5**: Document structure and forms.
- **CSS3**: Responsive styling and layout.
- **JavaScript**: Client-side interaction and dynamic UI.
- **Font Awesome**: Icons for button labels and navigation.

### Backend

- **Python**: Primary backend language.
- **Flask**: Web framework for API endpoints and routing.

### AI / Machine Learning

- **PaddleOCR**: OCR engine for text extraction from images.
- **OpenCV**: Image enhancement and preprocessing.
- **spaCy**: Named entity recognition for meaningful text extraction.
- **Regular Expressions**: Pattern-based extraction of document fields.

### Database

- **MySQL**: Stores user accounts, upload history, and document records.

### Key Python Libraries

- `paddleocr`
- `opencv-python`
- `spacy`
- `pandas`
- `numpy`
- `pillow`
- `pdf2image`
- `pymupdf`
- `python-docx`
- `pytesseract`

---

## Module Description

### Frontend Modules

- **Upload Module**: Handles drag-and-drop and file uploads.
- **Dashboard Module**: Displays extracted fields, history, and analytics.
- **Search Module**: Enables document search by keyword.
- **Export Module**: Exports results to JSON and CSV.

### Backend Modules

- **OCR Service**: Executes OCR operations and returns extracted text.
- **PDF Service**: Converts PDF pages to images and extracts text.
- **NLP Service**: Extracts structured fields and entities.
- **Document Intelligence**: Builds the final JSON payload and summary.
- **Export Service**: Generates JSON/CSV output.

### Utility Modules

- **File Utils**: File validation and sanitization.
- **Image Utils**: Preprocessing for OCR accuracy.
- **Progress Utils**: Real-time job progress updates.
- **Language Utils**: Language detection and label resolution.

---

## AI Workflow

1. The user uploads an image or PDF document.
2. The backend preprocesses the document using OpenCV.
3. The OCR service reads text using PaddleOCR or PDF native extraction.
4. The extracted text is analyzed by spaCy for entity recognition.
5. Regular expressions extract structured fields from the raw text.
6. The extracted data is organized into a compact JSON payload.
7. The dashboard displays the results and enables export.

### Sample Code Snippet

```python
from services.ocr_service import perform_ocr
from services.nlp_service import extract_information

ocr_result = perform_ocr(image_np, engine_choice="paddleocr", language="multilingual")
nlp_result = extract_information(ocr_result["text"], ocr_confidence=ocr_result["confidence"])
```

---

## Database Design

### Main Entities

- `users` — stores account details.
- `documents` — stores document metadata and extraction results.

### Entity Relationships

```text
users
+----+----------+----------------+
| id | username | password_hash  |
+----+----------+----------------+

documents
+----+---------+----------------+-----------------+
| id | user_id | filename       | extracted_data  |
+----+---------+----------------+-----------------+
```

### Notes

- Each document record is linked to a user.
- Extracted data is stored as JSON for flexibility.
- Uploaded files are saved in `uploads/` and outputs are archived under `extracted/`.

---

## API Flow

### Primary Endpoints

- `POST /extract` — Upload and process a document.
- `GET /progress/<job_id>` — Retrieve extraction progress.
- `GET /search` — Search previously processed documents.
- `GET /export/<fmt>` — Export the extraction result.

### Example Request

```bash
curl -X POST -F "file=@invoice.pdf" http://localhost:5000/extract
```

### Example Response

```json
{
  "document_type": "Invoice",
  "filename": "invoice.pdf",
  "language": "en",
  "overall_confidence": 97.8,
  "extracted_fields": {
    "invoice_number": "INV-1001",
    "invoice_date": "2026-08-05",
    "company_name": "ABC Pvt Ltd",
    "total_amount": "₹5,420"
  },
  "entities": [
    "ABC Pvt Ltd",
    "INV-1001"
  ],
  "ai_summary": "Invoice successfully processed with key information extracted.",
  "processing_time": "2.8 sec"
}
```

---

## Installation Steps

### Prerequisites

- Python 3.8 or higher
- Node.js 16 or higher
- MySQL database

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Running the Application

1. Start the backend server.
2. Start the frontend development server.
3. Open the browser and access the UI.

---

## Future Scope

- Add support for additional document types such as contracts, medical forms, and bank statements.
- Improve extraction accuracy with deep learning-based table extraction and layout modeling.
- Add handwriting recognition.
- Support multi-language OCR and multilingual entity extraction.
- Develop a SaaS-ready deployment with multi-tenant support.
- Add automated approval workflows and integration with third-party APIs.

---

## Advantages

- Automates document data extraction.
- Reduces manual entry and human error.
- Supports export to modern formats.
- Provides searchable history and dashboards.
- Improves productivity for invoice and document processing.

---

## Limitations

- OCR accuracy depends on document quality.
- Handwritten text extraction may be limited.
- Complex document layouts may require additional tuning.
- Regex-based extraction may miss irregular formats.

---

## Conclusion

The AI Document Understanding Platform is a complete internship/project-ready solution for document automation. It blends OCR, NLP, and structured extraction to convert unstructured documents into actionable data, making it ideal for real-world business workflows.

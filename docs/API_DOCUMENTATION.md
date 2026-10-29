# API Documentation — AI Document Understanding Platform

## 1. Authentication & Security Headers

The platform provides session-based authentication for browser and AJAX requests, as well as REST endpoints.

| Route / Feature | Auth Required | Accepted Roles | Response Format |
|---|---|---|---|
| User Ingestion & Extraction (`/api/v1/extract`) | Optional / Session | `user`, `admin`, Guest | `application/json` |
| Export Endpoints (`/api/v1/export/*`) | Optional / Session | `user`, `admin`, Guest | Binary / CSV / JSON |
| Admin REST APIs (`/api/admin/*`) | **Required** | `admin` Only | `application/json` |
| FastAPI Headless APIs (`/api/v1/documents/*`)| Standard REST | All clients | `application/json` |

---

## 2. Document Processing Endpoints (Flask API)

### 2.1. Extract Document Information
- **Endpoint**: `POST /api/v1/extract`
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `file` (binary, required): Image (`.png`, `.jpg`, `.jpeg`, `.tiff`, `.webp`) or PDF file.
  - `force_ocr` (boolean, optional): Force OCR execution even if native text is found in PDF.
- **Success Response (200 OK)**:
```json
{
  "job_id": "JOB-64C706F7",
  "filename": "invoice_sample.png",
  "document_type": "Invoice",
  "confidence_score": 0.94,
  "processing_time": "1.42s",
  "status": "Completed",
  "raw_text": "INVOICE #INV-2026-001\nDate: 2026-10-24\nTotal: $1,250.00...",
  "extracted_fields": [
    { "field": "invoice_number", "value": "INV-2026-001", "confidence": 0.98 },
    { "field": "total_amount", "value": "1250.00", "confidence": 0.95 },
    { "field": "date", "value": "2026-10-24", "confidence": 0.92 }
  ],
  "tables": [
    {
      "headers": ["Item Description", "Qty", "Unit Price", "Total"],
      "rows": [
        ["Cloud Hosting Services", "1", "1000.00", "1000.00"],
        ["Domain Registration", "1", "250.00", "250.00"]
      ]
    }
  ],
  "spacy_entities": [
    { "text": "Cloud Hosting Services", "label": "ORG" },
    { "text": "2026-10-24", "label": "DATE" },
    { "text": "1250.00", "label": "MONEY" }
  ]
}
```

### 2.2. Poll Processing Progress
- **Endpoint**: `GET /api/v1/progress/<job_id>`
- **Response**:
```json
{
  "job_id": "JOB-64C706F7",
  "stage": "OCR Processing",
  "progress_percent": 65,
  "status": "In Progress"
}
```

### 2.3. Run Sample Document (Demo Mode)
- **Endpoint**: `GET /api/v1/sample/<doc_type>`
- **Parameters**: `doc_type` = `invoice` | `receipt` | `medical` | `id`
- **Response**: Returns pre-computed full structured document analysis without requiring file upload.

---

## 3. Export Endpoints

### 3.1. Export to PDF Summary
- **Endpoint**: `GET /api/v1/export/pdf/<job_id>`
- **Response**: Formatted PDF document (`Content-Type: application/pdf`).

### 3.2. Export to CSV
- **Endpoint**: `GET /api/v1/export/csv/<job_id>`
- **Response**: Downloadable CSV table containing extracted fields and values.

### 3.3. Export to Raw JSON
- **Endpoint**: `GET /api/v1/export/json/<job_id>`
- **Response**: Full structured JSON payload.

---

## 4. Administrative REST APIs (Admin Only)

All endpoints under `/api/admin/` require an active administrator session.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/admin/overview` | Platform summary: total users, documents processed, success rate, error counts |
| `GET` | `/api/admin/users` | List managed users with roles, statuses, and last login dates |
| `POST` | `/api/admin/users` | Create a new user account under the active admin hierarchy |
| `POST` | `/api/admin/users/<id>/status` | Update account status (`active` or `blocked`) |
| `POST` | `/api/admin/users/<id>/password`| Reset user password |
| `GET` | `/api/admin/documents` | System-wide audit list of document jobs and confidence metrics |
| `GET` | `/api/admin/activity-logs` | Chronological activity and security audit trail |
| `GET` | `/api/admin/error-logs` | Application exception logs with stack traces |
| `GET` | `/api/admin/storage-metrics` | Disk usage for `uploads/`, `extracted/`, and database sizes |

---

## 5. FastAPI REST API (Headless Microservice)

When running the FastAPI server on port 8000:

- **Interactive Swagger UI**: `http://localhost:8000/api/docs`
- **ReDoc Interactive Reference**: `http://localhost:8000/api/redoc`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/documents/upload` | Upload document to FastAPI storage & trigger AI pipeline |
| `GET` | `/api/v1/documents/` | Paginated document listing (`skip`, `limit`) |
| `GET` | `/api/v1/documents/document/{id}` | Detailed document extraction by numerical ID |
| `DELETE` | `/api/v1/documents/document/{id}` | Delete document and associated output records |
| `GET` | `/api/v1/documents/dashboard/stats` | Aggregate classification & processing stats |

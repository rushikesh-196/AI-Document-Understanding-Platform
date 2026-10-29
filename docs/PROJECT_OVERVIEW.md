# Project Overview — AI Document Understanding Platform

## 1. Executive Summary

The **AI Document Understanding Platform** is an enterprise-grade document intelligence system designed to automate the ingestion, OCR parsing, classification, information extraction, structured reconstruction, and export of complex physical and digital documents (invoices, receipts, medical records, financial forms, identity documents).

The platform bridges computer vision (multi-engine OCR with PaddleOCR and PyMuPDF) and Natural Language Processing (spaCy Named Entity Recognition and regex pattern matching), backed by a dual-engine persistence layer (MySQL primary with automated SQLite local failover) and role-based access control (RBAC).

---

## 2. Problem Statement

Organizations process thousands of invoices, receipts, patient records, and identity files weekly. Traditional manual data entry and generic OCR solutions encounter persistent bottlenecks:
1. **Unstructured Data**: Plain OCR outputs noisy, unformatted blocks of text without semantics or relationships.
2. **Layout Fragility**: Multi-column documents, key-value pairings, and tabular data lose their spatial alignment.
3. **Data Quality & Hallucination Risks**: Cloud-only LLMs without verification can hallucinate critical numeric amounts, dates, or tax IDs.
4. **Security & Data Isolation**: Multi-tenant organizations require isolated user access and strict administrative auditing.

---

## 3. The Solution

This platform implements an end-to-end processing pipeline:
- **Image Preprocessing**: Deskewing, grayscale conversion, and noise filtering via OpenCV.
- **Multi-Engine OCR Strategy**: High-precision recognition using PaddleOCR with native PyMuPDF PDF text extraction fallback.
- **Rule-Based & Statistical Information Extraction**: Regex-driven pattern matching for financial entities (GSTIN, PAN, Invoice Number, Totals, Dates) cross-verified against spaCy tokenized entities.
- **Table & Layout Reconstruction**: Spatial bounding-box clustering to rebuild row-and-column tables.
- **Dual Presentation**: Full-stack Flask Web Application with Jinja2 interactive UI and a headless FastAPI + React 18 TypeScript SPA.
- **Enterprise RBAC**: Role isolation separating Administrators and Standard Users with full activity logging.

---

## 4. Key Capabilities & Implementation Status

| Feature | Description | Implementation Status |
|---|---|---|
| **Multi-Engine OCR** | PaddleOCR + PyMuPDF fallbacks | ✅ **Verified Active** |
| **Document Classification** | Rule-based & keyword weighting classifier | ✅ **Verified Active** |
| **Named Entity Recognition (NER)** | spaCy `en_core_web_sm` model | ✅ **Verified Active** |
| **Table Reconstruction** | Spatial heuristics & delimiter parsing | ✅ **Verified Active** |
| **Multi-Format Export** | JSON, CSV, and formatted PDF summaries | ✅ **Verified Active** |
| **Interactive User Dashboard** | Real-time progress, document history, stats | ✅ **Verified Active** |
| **Admin Management Portal** | RBAC, user management, audit trails, system health | ✅ **Verified Active** |
| **Password Management** | Bcrypt-hashed password changes with strength meter | ✅ **Verified Active** |
| **Sample Document Demo Mode** | Instant sample document testing without upload | ✅ **Verified Active** |
| **LLM Summarization** | Google Gemini API integration (optional) | ⚠️ **Optional / Configurable** |

---

## 5. User Roles and Permissions

1. **Standard User (`role='user'`)**:
   - Upload and process documents.
   - View own processing results, raw text, structured tables, and extracted entities.
   - Export results to JSON and CSV.
   - Manage personal profile and change passwords.
   - Access history restricted exclusively to own documents.

2. **Administrator (`role='admin'`)**:
   - Access dedicated Admin Portal (`/admin/dashboard`).
   - Create, monitor, block, and reactivate users under administrative hierarchy.
   - View platform-wide processing statistics, error logs, and activity audit trails.
   - Monitor storage utilization and processing queues.
   - Tenant isolation: Admins manage exclusively their own organization's users unless designated as Super Administrator.

# AI Document Understanding Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![PaddleOCR](https://img.shields.io/badge/OCR-PaddleOCR%20%7C%20PyMuPDF-FF6F00)](https://github.com/PaddlePaddle/PaddleOCR)
[![spaCy](https://img.shields.io/badge/NLP-spaCy%203.7-09A3D5?logo=spacy&logoColor=white)](https://spacy.io)
[![MySQL](https://img.shields.io/badge/Database-MySQL%20%2B%20SQLite%20Fallback-4479A1?logo=mysql&logoColor=white)](https://mysql.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-30%2F30%20Passing-brightgreen)](tests/)

> An end-to-end, enterprise-ready document intelligence platform that automates ingestion, text extraction, spatial table reconstruction, named entity recognition, and multi-format reporting across physical scans and digital documents. Built with a dual-architecture supporting a server-rendered Flask web application with enterprise RBAC, plus a headless FastAPI microservice and React 18 TypeScript SPA.

---

## Quick Links & Documentation Suite

For comprehensive technical specifications, explore the modular documentation in [docs/](docs/):

- **[Project Overview](docs/PROJECT_OVERVIEW.md)**: Problem statement, user roles, feature status matrix.
- **[System Architecture](docs/ARCHITECTURE.md)**: Decoupled dual-tier design, pipeline flow, and Mermaid diagrams.
- **[Folder Structure](docs/FOLDER_STRUCTURE.md)**: Complete file inventory and directory responsibilities.
- **[Setup & Execution](docs/SETUP_AND_EXECUTION.md)**: Step-by-step installation, script launchers, and troubleshooting.
- **[API Documentation](docs/API_DOCUMENTATION.md)**: Detailed endpoints, request payloads, and JSON response schemas.
- **[Database Schema](docs/DATABASE_SCHEMA.md)**: MySQL & SQLite dual-engine tables, columns, and relations.
- **[Security & Governance](docs/SECURITY.md)**: RBAC model, password hashing, and cookie hardening.
- **[Testing Guide](docs/TESTING.md)**: Test suites, execution procedures, and CI workflows.

---

## 1. Key Features & Implementation Status

| Feature Name | Description | Status |
|---|---|:---:|
| **Multi-Engine OCR** | PaddleOCR with native PyMuPDF PDF text extraction fallback | Implemented |
| **Document Classification** | Rule-based and keyword weighting classifier (Invoice, Receipt, Medical, ID) | Implemented |
| **Named Entity Recognition** | spaCy (en_core_web_sm) tokenization and entity extraction (Org, Date, Money) | Implemented |
| **Table Reconstruction** | Spatial bounding-box parsing to rebuild structured tabular columns and rows | Implemented |
| **Enterprise RBAC & Auth** | PBKDF2-HMAC-SHA256 password hashing, session tokens, and admin hierarchy | Implemented |
| **Admin Management Portal** | Dedicated portal with 9 views: user management, storage metrics, audit logs | Implemented |
| **Sample Demo Mode** | Instant one-click processing for sample documents without file uploads | Implemented |
| **Multi-Format Export** | Download results dynamically as structured PDF summaries, CSVs, or JSON | Implemented |
| **Dual-Engine Persistence** | MySQL 8.0 primary with transparent fallback to embedded SQLite | Implemented |
| **Dual Architecture** | Flask Full-Stack UI (:5000) + FastAPI (:8000) & React 18 SPA (:3000) | Implemented |
| **Automated Test Suite** | 30 unit & integration tests passing with 100% pass rate | Implemented |
| **LLM Summarization** | Google Gemini API integration (optional cloud extension) | Configurable |

---

## 2. Problem Statement

Organizations ingest thousands of unstructured paper invoices, medical bills, allotment letters, and receipts daily. Traditional data processing involves manual data entry, which is error-prone, slow, and expensive. Generic OCR engines only output raw text without semantic context, layout awareness, or tabular structure. Furthermore, enterprise document workflows require strict user isolation, administrative audit trails, and reliable offline persistence.

---

## 3. Solution & Workflow

The platform provides a streamlined document processing pipeline:
1. **Ingestion & Validation**: Upload documents with strict MIME type checking, extension validation, and a 16 MB limit.
2. **Preprocessing**: Images are deskewed, noise-reduced, and binarized using OpenCV.
3. **Multi-Engine Extraction**: PaddleOCR detects text with bounding boxes; PyMuPDF handles native vector PDFs.
4. **Information Extraction & NER**: spaCy extracts named entities, while tailored regular expressions extract invoice numbers, tax IDs (GST/PAN), dates, and totals.
5. **Spatial Layout & Table Reconstruction**: Delimiters and bounding boxes align columns and rows into structured tables.
6. **Review & Export**: Results are reviewed in interactive dashboards and exported to structured PDF, CSV, or JSON.

---

## 4. Technology Stack

### Backend & AI Pipelines (Verified)
- **Frameworks**: Flask 3.x (Full-Stack), FastAPI 0.109 (Headless API), Werkzeug
- **OCR Engines**: PaddleOCR 2.7+, paddlepaddle 2.5+, PyMuPDF (fitz) 1.23+
- **Computer Vision**: OpenCV (opencv-python 4.8+)
- **Natural Language Processing**: spaCy 3.7+ (en_core_web_sm)
- **Document Generation**: ReportLab 4.0+ (PDF), pandas 2.0+ (CSV), python-docx
- **Databases**: MySQL 8.0 (mysql-connector-python 9.0+) with SQLite 3 fallback

### Frontend (Verified)
- **Framework**: React 18.2 with TypeScript 5.3
- **Build Tool**: Vite 5.0
- **Styling**: Tailwind CSS 3.4, PostCSS, Lucide React icons
- **State & Data Visualization**: React Context, Recharts 2.10, Axios

---

## 5. System Architecture

## 5. System Architecture

```mermaid
flowchart TD
    A["User Browser / React SPA"] --> B["Web Tier Router"]

    B --> C["Flask Server (Port 5000)"]
    B --> D["FastAPI Server (Port 8000)"]

    C --> E["Jinja2 Server-Rendered UI"]
    C --> F["RBAC Admin"]

    D --> G["Headless REST Endpoints (/api/v1)"]

    G --> H["Document Intelligence Pipeline"]

    H --> I["1. Image Preprocessing (OpenCV)"]
    I --> J["2. OCR Engine (PaddleOCR / PyMuPDF)"]
    J --> K["3. NLP & Pattern Extraction (spaCy NER / RegEx)"]
    K --> L["4. Spatial Layout Reconstruction (Tables & Cell Alignment)"]

    L --> M["Data Layer"]

    M --> N["MySQL (Primary Database)"]
    M --> O["SQLite (Automatic Fallback)"]
    M --> P["File Storage (uploads/, extracted/, outputs/)"]
```

---

## 6. Project Structure

## 6. Project Structure

```text
AI-Document-Understanding-Platform/
├── README.md                      # Placement-ready documentation
├── LICENSE                        # MIT License
├── .gitignore                     # Production Git ignore rules
├── .env.example                   # Sanitized environment template
├── requirements.txt               # Root Python dependencies
├── plan.md                        # Project roadmap and notes
│
├── docs/                          # Technical documentation
│   ├── PROJECT_OVERVIEW.md        # Features, roles, requirements
│   ├── ARCHITECTURE.md            # Architecture and flow diagrams
│   ├── FOLDER_STRUCTURE.md        # Directory responsibilities
│   ├── SETUP_AND_EXECUTION.md     # Installation and startup guide
│   ├── API_DOCUMENTATION.md       # API endpoints and schemas
│   ├── DATABASE_SCHEMA.md         # Tables, columns, relationships
│   ├── SECURITY.md                # RBAC and security practices
│   └── TESTING.md                 # Test plan and verification
│
├── routes/                        # Flask controllers
├── services/                      # OCR, NLP, database and auth services
├── models/                        # ML models and classification pipelines
├── utils/                         # Reusable utility functions
├── templates/                     # Flask Jinja2 templates
│   └── admin/                     # Admin interface templates
├── static/                        # CSS, JavaScript and sample documents
├── tests/                         # Pytest test suite
│
├── backend/                       # FastAPI backend and AI models
│   ├── app/                       # API, models and schemas
│   ├── document_ai.db             # SQLite development database
│   ├── requirements.txt           # Backend dependencies
│   └── README.md                  # Backend documentation
│
├── frontend/                      # React + TypeScript + Vite
│   ├── src/                       # Components, pages and services
│   ├── package.json               # Frontend dependencies and scripts
│   ├── vite.config.ts              # Vite configuration and API proxy
│   └── README.md                  # Frontend documentation
│
├── data/                          # SQLite fallback and backups
├── scripts/                       # Startup and automation scripts
│   ├── start_server.ps1           # Flask platform launcher
│   ├── start.bat                  # Windows batch launcher
│   ├── start_fastapi.ps1           # FastAPI launcher
│   └── setup.ps1                  # Environment setup script
│
├── START_SERVER.ps1               # Root PowerShell launcher
├── START.bat                      # Root batch launcher
├── uploads/                       # Uploaded document storage
└── extracted/                     # Structured extraction outputs
```


---

## 7. Prerequisites & Installation

### Prerequisites
- **Python**: 3.10+ (tested on Python 3.10.11)
- **Node.js**: 18+ (only needed if running React frontend)
- **MySQL 8.0** (optional; automatically falls back to SQLite)

### One-Click Automated Setup (PowerShell)
`powershell
.\scripts\setup.ps1
`

### Manual Setup
`ash
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1    # On Windows PowerShell
# source venv/bin/activate     # On Linux / macOS

# 2. Install dependencies & language models
pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 3. Create environment file
cp .env.example .env
`

---

## 8. Running the Application

### Option A: Production Flask Web Application (Recommended)

Run via the automated PowerShell script:
`powershell
.\START_SERVER.ps1
# or
.\scripts\start_server.ps1
`

Or via direct command:
`ash
python app.py
`

The application will launch on **http://127.0.0.1:5000** and automatically open in your default browser.

### Option B: Headless FastAPI Backend & React SPA

`powershell
# Terminal 1: Start FastAPI Backend (Port 8000)
.\scripts\start_fastapi.ps1

# Terminal 2: Start React Frontend (Port 3000)
cd frontend
npm install
npm run dev
`

---

## 9. Application URLs & Default Accounts

| Application Area | URL | Default Access |
|---|---|---|
| **Landing & Upload** | http://127.0.0.1:5000 | Public / Guest |
| **Document Upload** | http://127.0.0.1:5000/upload | User / Admin |
| **Extraction Results** | http://127.0.0.1:5000/results | User / Admin |
| **User Dashboard** | http://127.0.0.1:5000/dashboard | User / Admin |
| **Admin Portal** | http://127.0.0.1:5000/auth?portal=admin | Admin Only |
| **FastAPI Swagger Docs**| http://127.0.0.1:8000/api/docs | Developer |
| **React SPA** | http://localhost:3000 | User |

### Default Development Accounts
- **System Administrator**: dmin@docintel.io / Admin@123456
- **Standard User**: user@docintel.io / User@123456

*(Seeded for development. For production deployments, change these passwords immediately or run python create_admin.py).*

---

## 10. API Endpoints Overview

| Method | Endpoint | Description | Auth Required |
|---|---|---|:---:|
| POST | /api/v1/extract | Upload document and trigger OCR + extraction pipeline | Optional |
| GET | /api/v1/progress/<job_id> | Real-time progress percentage and current stage polling | No |
| GET | /api/v1/sample/<doc_type> | Demo mode: returns pre-extracted analysis for sample files | No |
| GET | /api/v1/export/pdf/<job_id> | Export structured analysis to formatted PDF | Optional |
| GET | /api/v1/export/csv/<job_id> | Export extracted fields to tabular CSV | Optional |
| GET | /api/v1/export/json/<job_id> | Export raw structured JSON data | Optional |
| GET | /api/admin/overview | Platform health: users, processing throughput, success rate | **Admin** |
| GET | /api/admin/users | List managed users with roles, statuses, and login dates | **Admin** |
| POST | /api/admin/users/<id>/status | Update account status (ctive or locked) | **Admin** |
| GET | /api/admin/activity-logs | Chronological security and operational audit trail | **Admin** |
| GET | /api/admin/storage-metrics | Storage consumption for uploads, extracted data, and DB | **Admin** |

*For complete API schemas and curl examples, see [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md).*

---

## 11. Database Management & Failover

The platform uses a resilient **dual-engine database architecture**:
- **Primary**: MySQL 8.0 on localhost:3306 with connection pooling.
- **Failover**: If MySQL is unreachable, the system automatically switches to the embedded SQLite database (data/document_platform.db) with zero downtime or manual intervention.
- **Audit Trails**: Security actions and administrative interventions are recorded in the ctivity_logs table.

*For schema details, column types, and constraints, see [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md).*

---

## 12. Testing & Verification

Run the automated Pytest test suite:

`powershell
pytest tests/
`

**Results:**
- **30 / 30 Tests Passing (100% Pass Rate)** across Admin RBAC, authentication, dashboard routes, document intelligence synthesis, export services, and layout reconstruction.

Run the end-to-end admin verification suite:
`ash
python tests/run_tests.py
`
**Results:**
- **10 / 10 Integration Suites Passing**, verifying tenant isolation, account blocking, admin hierarchies, and route security.

*For detailed test commands, coverage metrics, and CI workflows, see [docs/TESTING.md](docs/TESTING.md).*

---

## 13. Security & Governance

- **Password Hashing**: PBKDF2-HMAC-SHA256 with dynamic salts.
- **Session Protection**: SESSION_COOKIE_HTTPONLY=True (guards against XSS), SESSION_COOKIE_SAMESITE='Lax' (mitigates CSRF).
- **File Validation**: Strict MIME inspection, filename sanitization with secure_filename, and a 16 MB maximum size limit.
- **SQL Injection Defense**: Parameterized SQL statements across MySQL and SQLite.
- **Secret Hygiene**: Zero hardcoded secrets committed. Sanitized .env.example provided.

*For threat models and production deployment guidelines, see [docs/SECURITY.md](docs/SECURITY.md).*

---

## 14. Known Limitations & Roadmap

### Known Limitations
- Heavy OCR libraries (PaddlePaddle, PyTorch) require ~5-10 seconds to load during cold boot.
- spaCy en_core_web_sm is optimized for general English text; specialized medical terminology relies primarily on rule-based extractors.

### Planned Improvements
- [ ] Add Docker and docker-compose.yml for unified one-command deployment.
- [ ] Implement Celery + Redis worker queue for asynchronous background batch processing.
- [ ] Fine-tune custom LayoutLMv3 weights specifically on Indian tax invoices and medical receipts.
- [ ] Add multi-page PDF bounding box interactive overlay in the results view.

---

## 15. License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

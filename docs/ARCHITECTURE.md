# System Architecture — AI Document Understanding Platform

## 1. High-Level Architecture Overview

The system is engineered using a modular, decoupled architecture supporting both a full-stack monolithic web application and a decoupled headless API tier:

```mermaid
flowchart TD
    subgraph Clients["Client Presentation Tier"]
        Browser["User Browser (Desktop / Mobile)"]
        SPA["React 18 TypeScript SPA (:3000)"]
    end

    subgraph WebTier["Application & API Tier"]
        FlaskServer["Flask Production Server (:5000)\n(Routes: OCR, Admin, Auth, Export)"]
        FastAPIServer["FastAPI Headless Server (:8000)\n(Modular REST Endpoints /api/v1)"]
    end

    subgraph EngineTier["AI & Document Processing Pipeline"]
        PreProc["OpenCV Image Preprocessing"]
        OCR["PaddleOCR & PyMuPDF Engine"]
        NLP["spaCy NER + Regex Field Extractors"]
        Layout["Spatial Table & Layout Reconstructor"]
        LLM["Optional Gemini LLM Integration"]
    end

    subgraph DataTier["Persistence & Storage Tier"]
        MySQL[("MySQL 8.0 Primary DB\n(Users, RBAC, Jobs, Audits)")]
        SQLite[("SQLite Fallback DB\n(data/document_platform.db)")]
        FileStore["File Storage System\n(uploads/, extracted/, outputs/)"]
    end

    Browser -->|HTTP / Jinja2 SSR| FlaskServer
    SPA -->|Vite Proxy /api/v1| FastAPIServer
    FlaskServer --> PreProc
    FastAPIServer --> PreProc
    PreProc --> OCR
    OCR --> NLP
    NLP --> Layout
    Layout --> LLM
    FlaskServer --> MySQL
    FlaskServer -.->|Failover| SQLite
    FastAPIServer --> SQLite
    FlaskServer --> FileStore
```

---

## 2. Document Processing & OCR Pipeline

The document pipeline transforms unstructured image or PDF inputs into validated structured records:

```mermaid
sequenceDiagram
    autonumber
    actor User as Client / User
    participant App as Flask Backend
    participant File as File Storage (uploads/)
    participant OCR as OCR Engine (PaddleOCR)
    participant NLP as spaCy + Pattern Extraction
    participant Layout as Layout & Table Reconstructor
    participant DB as Persistence Layer (MySQL/SQLite)

    User->>App: POST /api/v1/extract (Document File)
    App->>File: Save file with Unique Job ID (JOB-XXXXXXXX)
    App->>App: Validate MIME type & file extension
    App->>OCR: Preprocess image & run text recognition
    OCR-->>App: Raw text + Bounding Boxes + Confidence scores
    App->>NLP: Run Named Entity Recognition & Regex extraction
    NLP-->>App: Entities (Org, Person, Date, Money) & Fields (GST, Totals, PAN)
    App->>Layout: Reconstruct tabular structures & alignments
    Layout-->>App: Structured Tables & Layout JSON
    App->>File: Write JOB-XXXXXXXX.json to extracted/ & outputs/
    App->>DB: Record document job, timing, confidence, and status
    App-->>User: Return HTTP 200 with structured analysis JSON
```

---

## 3. Dual-Tier Server Architecture

### Tier 1: Flask Full-Stack Platform (Port 5000)
- **Primary Operational Platform**: Powered by Flask 3.x, serving Jinja2 templates directly to browsers.
- **Components**:
  - `routes/ocr_routes.py`: Upload ingestion, OCR processing, asynchronous progress tracking, sample document demo endpoints.
  - `routes/admin_routes.py`: Protected administrative controllers for RBAC management, audit viewing, and monitoring.
  - `routes/export_routes.py`: Dynamic generation of PDF summaries and CSV exports.
  - `routes/dashboard_routes.py`: Dashboard stats aggregation and job history filtering.

### Tier 2: FastAPI Headless API & React SPA (Ports 8000 & 3000)
- **Modular Microservice**: Powered by FastAPI 0.109 with SQLAlchemy models and Pydantic validation schemas.
- **Frontend SPA**: React 18 with TypeScript, Tailwind CSS, Lucide icons, and Recharts, configured via Vite proxy (`/api -> localhost:8000`).
- **AI Models**: Integrates LayoutLMv3 sequence classification alongside PaddleOCR and spaCy.

---

## 4. Authentication & RBAC Authorization Flow

```mermaid
flowchart TD
    LoginRequest["Login Request (Email, Password, Target Portal)"] --> AuthCheck{"Authenticate User"}
    AuthCheck -->|Invalid Password / Inactive| Deny["401 Unauthorized / Account Blocked"]
    AuthCheck -->|Valid Credentials| RoleCheck{"Check Role & Target Portal"}
    RoleCheck -->|Role: user, Portal: admin| Forbidden["403 Forbidden\n(Admins Only)"]
    RoleCheck -->|Role: admin, Portal: admin| AdminSession["Create Admin Session\nRedirect -> /admin/dashboard"]
    RoleCheck -->|Role: user, Portal: user| UserSession["Create User Session\nRedirect -> /dashboard"]
```

- Passwords are encrypted using Werkzeug's secure password hash generation (PBKDF2-HMAC-SHA256).
- Session cookies are protected with `HttpOnly` and `SameSite=Lax` flags to prevent XSS cross-site scripting attacks.

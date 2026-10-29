# Folder Structure & Directory Responsibilities

## 1. Directory Tree Overview

```
AI-Document-Understanding-Platform/
├── README.md                      # Primary placement-ready documentation
├── LICENSE                        # MIT Open Source License
├── .gitignore                     # Git ignore rules for caches, builds, uploads, DBs
├── .env.example                   # Environment configuration template
├── requirements.txt               # Root Python dependencies for Flask application
├── plan.md                        # Historical roadmap & LLM integration notes
│
├── docs/                          # Comprehensive Technical Documentation
│   ├── PROJECT_OVERVIEW.md        # Problem statement, features, user roles
│   ├── ARCHITECTURE.md            # System architecture, sequence, and flow diagrams
│   ├── FOLDER_STRUCTURE.md        # Detailed directory and module guide (this file)
│   ├── SETUP_AND_EXECUTION.md     # Installation and execution instructions
│   ├── API_DOCUMENTATION.md       # API routes and parameters specification
│   ├── DATABASE_SCHEMA.md         # Schema tables, relations, and persistence rules
│   ├── SECURITY.md                # Security controls, RBAC, and best practices
│   └── TESTING.md                 # Test plan, suites, commands, and verification
│
├── backend/                       # Headless FastAPI Backend & ML Models
│   ├── app/                       # FastAPI application package
│   │   ├── api/v1/endpoints/      # API endpoints (/documents/upload, /documents)
│   │   ├── core/                  # FastAPI settings and config
│   │   ├── db/                    # SQLAlchemy database session
│   │   ├── models/                # SQLAlchemy database models
│   │   ├── schemas/               # Pydantic serialization schemas
│   │   └── services/ai/           # Classification, NER, Layout, and Summary services
│   ├── document_ai.db             # FastAPI SQLite development database
│   ├── requirements.txt           # FastAPI-specific Python dependencies
│   ├── .env.example               # FastAPI environment template
│   └── README.md                  # FastAPI documentation
│
├── frontend/                      # React 18 + TypeScript + Vite Single-Page Application
│   ├── src/                       # Frontend source code
│   │   ├── components/            # Reusable UI widgets & Shared Layout
│   │   ├── context/               # React Context (ThemeContext for Dark/Light mode)
│   │   ├── pages/                 # Route screens (Upload, Dashboard, History, DocumentView)
│   │   ├── services/              # Axios API service client
│   │   ├── types/                 # Shared TypeScript interfaces
│   │   ├── utils/                 # Utility functions (Tailwind clsx / cn)
│   │   ├── App.tsx                # Main App component with React Router
│   │   └── main.tsx               # Frontend bootstrap entry point
│   ├── index.html                 # Single page application HTML shell
│   ├── package.json               # NPM packages & build scripts
│   ├── tsconfig.json              # TypeScript compilation rules
│   ├── vite.config.ts             # Vite server & API proxy (/api -> :8000)
│   └── README.md                  # Frontend documentation
│
├── routes/                        # Flask HTTP Blueprints & Controllers
│   ├── admin_routes.py            # RBAC management, audit viewing, storage metrics
│   ├── dashboard_routes.py        # Dashboard analytics & job list filtering
│   ├── export_routes.py           # Structured PDF and CSV export endpoints
│   ├── history_routes.py          # Paginated document processing history
│   ├── ocr_routes.py              # OCR extraction, progress polling, sample demo routes
│   ├── upload_routes.py           # File upload handling & validation
│   └── __init__.py                # Blueprint exports & initialization
│
├── services/                      # Flask Business Logic & AI Services
│   ├── admin_service.py           # Admin analytics, user status management, audits
│   ├── auth_service.py            # User registration, password hashing, authentication
│   ├── database.py                # Dual-engine DB manager (MySQL primary + SQLite fallback)
│   ├── document_intelligence.py   # Table detection, layout synthesis, entity grouping
│   ├── export_service.py          # PDF document generation & CSV data compilation
│   ├── extraction_service.py      # Field extraction (GST, PAN, dates, amounts, invoice #)
│   ├── layout_reconstruction.py   # Spatial layout clustering & coordinate parsing
│   ├── llm_service.py             # Optional Gemini LLM extraction & summarization
│   ├── nlp_service.py             # spaCy tokenization, POS tagging, and entity extraction
│   ├── ocr_service.py             # Multi-engine OCR execution (PaddleOCR + PyMuPDF)
│   ├── pdf_service.py             # PDF text extraction and image rasterization
│   ├── validation_service.py      # Business rule validation for extracted entities
│   └── __init__.py                # Services module exports
│
├── models/                        # ML Model Implementations
│   ├── classifier.py              # Document type classifier (Invoice, Receipt, Medical, ID)
│   └── __init__.py                # Models module exports
│
├── utils/                         # Reusable Utility Functions
│   ├── cache_utils.py             # In-memory document caching layer
│   ├── file_utils.py              # Path sanitization, MIME detection, extension checks
│   ├── image_utils.py             # OpenCV deskewing, binarization, contrast adjustment
│   ├── language_utils.py          # Multilingual text cleaning & normalization
│   ├── progress_utils.py          # Real-time multi-stage job progress tracking
│   └── __init__.py                # Utils module exports
│
├── templates/                     # Flask Jinja2 Server-Rendered Views
│   ├── admin/                     # Administrative Portal Views
│   │   ├── activity_logs.html     # Security and activity audit log viewer
│   │   ├── admin_base.html        # Admin shell layout with sidebar and navbar
│   │   ├── analytics.html         # Document throughput & performance graphs
│   │   ├── dashboard.html         # Admin dashboard summary tiles
│   │   ├── documents.html         # System-wide document management table
│   │   ├── error_logs.html        # Application exception & error stack traces
│   │   ├── processing_monitor.html# Live OCR queue monitoring view
│   │   ├── storage.html           # Disk usage and database storage stats
│   │   └── users.html             # User creation, role toggling, and block/unblock
│   ├── auth.html                  # Tabbed Login / Registration form
│   ├── base.html                  # Global UI wrapper with navbar and theme support
│   ├── dashboard.html             # User document analytics & metrics
│   ├── history.html               # User historical document list
│   ├── index.html                 # SaaS marketing landing page
│   ├── results.html               # Structured OCR result review & JSON viewer
│   ├── settings.html              # Profile & secure password change interface
│   └── upload.html                # Drag-and-drop document upload interface
│
├── static/                        # Flask Static Assets
│   ├── css/                       # Custom responsive stylesheets
│   ├── js/                        # Client-side JavaScript (AJAX, charts, upload handlers)
│   └── samples/                   # Pre-bundled demo documents (Invoice, Receipt, Medical, ID)
│
├── tests/                         # Pytest Automated Test Suite (30 Tests)
│   ├── conftest.py                # Pytest configuration & sys.path setup
│   ├── run_tests.py               # Standalone runner for 10 RBAC verification test suites
│   ├── test_admin_system.py       # Admin authentication & RBAC unit tests
│   ├── test_auth_system.py        # Registration, hashing, and login tests
│   ├── test_dashboard_routes.py   # Dashboard endpoint tests
│   ├── test_document_intelligence.py # Table and entity synthesis tests
│   ├── test_export_service.py     # PDF & CSV generation tests
│   └── test_layout_reconstruction.py # Coordinate bounding-box tests
│
├── data/                          # Persistent Storage & Database
│   ├── .gitkeep                   # Git retention marker
│   ├── README.md                  # Database and persistence policy
│   └── document_platform.db       # Local SQLite database file (gitignored)
│
├── scripts/                       # Management & Automation Scripts
│   ├── start_server.ps1           # Production Flask launcher with port conflict detection
│   ├── start.bat                  # Windows batch launcher
│   ├── start_fastapi.ps1          # FastAPI server launcher
│   └── setup.ps1                  # One-click environment bootstrap & setup script
│
├── START_SERVER.ps1               # Root launcher convenience forwarder
├── START.bat                      # Root batch convenience forwarder
│
├── uploads/                       # Document storage directory for user uploads (gitignored)
├── extracted/                     # Structured JSON extraction results (gitignored)
└── outputs/                       # Backward-compatibility extraction mirror (gitignored)
```

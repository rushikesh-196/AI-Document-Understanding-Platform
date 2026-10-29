# Backend - AI Document Understanding Platform

FastAPI backend with AI-powered document processing capabilities.

## Tech Stack

- **Framework**: FastAPI 0.109.0
- **Database**: SQLAlchemy 2.0.25 with SQLite/PostgreSQL
- **AI Models**: 
  - LayoutLMv3 (Document Classification)
  - PaddleOCR (Multilingual OCR)
  - spaCy (Named Entity Recognition)
- **Python Version**: 3.8+

## Installation

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

## Running the Server

Development:
```bash
python -m app.main
```

Production:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Project Structure

```
backend/
├── app/
│   ├── api/v1/endpoints/    # API endpoints
│   ├── core/                # Configuration
│   ├── db/                  # Database setup
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── services/ai/         # AI services
│   ├── utils/               # Utilities
│   └── main.py              # Application entry
├── uploads/                 # File uploads
├── exports/                 # Exported files
└── requirements.txt
```

## AI Services

### OCR Service
- Supports PDF, JPG, PNG, TIFF
- Multilingual: English, Hindi, Marathi
- Returns text with confidence scores

### Classification Service
- Uses LayoutLMv3 for document classification
- 15+ document types supported
- Confidence scores and probabilities

### Layout Analysis Service
- Detects headers, footers, tables, images
- Identifies logos, signatures, QR codes
- Bounding box visualization

### NER Service
- Extracts named entities
- Supports custom entity types
- Color-coded visualization

### Extraction Service
- Type-specific field extraction
- Invoice, Resume, Bank Statement, IDs
- Missing field detection

### Summary Service
- AI-powered document summaries
- Key information extraction
- Warnings and recommendations

## Environment Variables

Key variables in `.env`:
- `DATABASE_URL` - Database connection
- `SECRET_KEY` - Security key
- `BACKEND_CORS_ORIGINS` - CORS settings
- `DEVICE` - AI device (cpu/cuda)
- `OCR_ENGINE` - OCR engine selection

## Database Models

### Document
- Stores document metadata
- Processing status and results
- AI confidence scores
- Extracted data and entities

### DocumentExport
- Export history
- Format tracking
- File path management

## Development

### Adding New AI Services
1. Create service in `app/services/ai/`
2. Import in `app/services/ai/__init__.py`
3. Use in endpoints or processing pipeline

### Adding New Endpoints
1. Create endpoint in `app/api/v1/endpoints/`
2. Add schemas in `app/schemas/`
3. Register in `app/api/v1/api.py`

## Testing

Run tests:
```bash
pytest tests/
```

## Deployment

### Docker
```bash
docker build -t docai-backend .
docker run -p 8000:8000 docai-backend
```

### Manual
1. Set production environment variables
2. Use PostgreSQL for database
3. Run with gunicorn/uvicorn workers
4. Set up reverse proxy (nginx)

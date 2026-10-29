"""
Document Database Models
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.db.session import Base


class DocumentType(str, enum.Enum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    RESUME = "resume"
    PASSPORT = "passport"
    AADHAAR = "aadhaar"
    PAN_CARD = "pan_card"
    DRIVING_LICENSE = "driving_license"
    BANK_STATEMENT = "bank_statement"
    MEDICAL_REPORT = "medical_report"
    CERTIFICATE = "certificate"
    RESEARCH_PAPER = "research_paper"
    UTILITY_BILL = "utility_bill"
    CONTRACT = "contract"
    INSURANCE = "insurance"
    TAX_DOCUMENT = "tax_document"
    OTHER = "other"


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    
    # Document Classification
    document_type = Column(SQLEnum(DocumentType), default=DocumentType.OTHER)
    classification_confidence = Column(Float, default=0.0)
    classification_probabilities = Column(JSON)
    
    # Processing Status
    status = Column(SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING)
    processing_started_at = Column(DateTime)
    processing_completed_at = Column(DateTime)
    processing_duration = Column(Float)  # in seconds
    
    # OCR Results
    ocr_text = Column(Text)
    ocr_confidence = Column(Float, default=0.0)
    language_detected = Column(String)
    
    # Layout Analysis
    layout_analysis = Column(JSON)
    
    # Named Entity Recognition
    entities = Column(JSON)
    
    # Information Extraction
    extracted_data = Column(JSON)
    
    # AI Summary
    summary = Column(Text)
    
    # Confidence Scores
    ocr_confidence_score = Column(Float, default=0.0)
    classification_confidence_score = Column(Float, default=0.0)
    layout_confidence_score = Column(Float, default=0.0)
    entity_confidence_score = Column(Float, default=0.0)
    extraction_confidence_score = Column(Float, default=0.0)
    overall_confidence_score = Column(Float, default=0.0)
    
    # Metadata
    upload_ip = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    exports = relationship("DocumentExport", back_populates="document", cascade="all, delete-orphan")


class DocumentExport(Base):
    __tablename__ = "document_exports"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    export_format = Column(String, nullable=False)  # json, csv, txt
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="exports")

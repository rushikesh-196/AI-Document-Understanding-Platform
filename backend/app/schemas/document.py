"""
Document Schemas for Request/Response Validation
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.document import DocumentType, ProcessingStatus


class DocumentBase(BaseModel):
    filename: str
    original_filename: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None


class DocumentCreate(DocumentBase):
    file_path: str


class DocumentUpdate(BaseModel):
    document_type: Optional[DocumentType] = None
    status: Optional[ProcessingStatus] = None
    ocr_text: Optional[str] = None
    summary: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None


class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_path: str
    file_size: Optional[int]
    mime_type: Optional[str]
    document_type: DocumentType
    classification_confidence: float
    classification_probabilities: Optional[Dict[str, float]]
    status: ProcessingStatus
    processing_started_at: Optional[datetime]
    processing_completed_at: Optional[datetime]
    processing_duration: Optional[float]
    ocr_text: Optional[str]
    ocr_confidence: float
    language_detected: Optional[str]
    layout_analysis: Optional[Dict[str, Any]]
    entities: Optional[List[Dict[str, Any]]]
    extracted_data: Optional[Dict[str, Any]]
    summary: Optional[str]
    ocr_confidence_score: float
    classification_confidence_score: float
    layout_confidence_score: float
    entity_confidence_score: float
    extraction_confidence_score: float
    overall_confidence_score: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentClassification(BaseModel):
    document_type: DocumentType
    confidence: float
    probabilities: Dict[str, float]


class LayoutAnalysis(BaseModel):
    headers: List[Dict[str, Any]]
    footers: List[Dict[str, Any]]
    paragraphs: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    logos: List[Dict[str, Any]]
    signatures: List[Dict[str, Any]]
    qr_codes: List[Dict[str, Any]]
    stamps: List[Dict[str, Any]]
    forms: List[Dict[str, Any]]
    text_blocks: List[Dict[str, Any]]


class Entity(BaseModel):
    text: str
    label: str
    start: int
    end: int
    confidence: float


class EntityExtraction(BaseModel):
    entities: List[Entity]
    confidence: float


class InformationExtraction(BaseModel):
    extracted_data: Dict[str, Any]
    confidence: float
    missing_fields: List[str]
    warnings: List[str]


class AISummary(BaseModel):
    summary: str
    purpose: str
    key_information: List[str]
    important_dates: List[str]
    financial_details: Optional[Dict[str, Any]]
    missing_fields: List[str]
    warnings: List[str]


class ConfidenceScores(BaseModel):
    ocr_confidence: float
    classification_confidence: float
    layout_confidence: float
    entity_confidence: float
    extraction_confidence: float
    overall_confidence: float


class DocumentSearch(BaseModel):
    query: str
    document_type: Optional[DocumentType] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class ExportRequest(BaseModel):
    format: str = Field(..., description="Export format: json, csv, txt")
    include_raw_text: bool = True
    include_entities: bool = True
    include_layout: bool = False


class ExportResponse(BaseModel):
    export_id: int
    document_id: int
    format: str
    file_path: str
    created_at: datetime


class DashboardStats(BaseModel):
    total_documents: int
    processing_documents: int
    completed_documents: int
    failed_documents: int
    average_confidence: float
    average_processing_time: float
    document_type_distribution: Dict[str, int]
    recent_uploads: List[DocumentResponse]

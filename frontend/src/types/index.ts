export interface Document {
  id: number;
  filename: string;
  original_filename: string;
  file_path: string;
  file_size?: number;
  mime_type?: string;
  document_type: DocumentType;
  classification_confidence: number;
  classification_probabilities?: Record<string, number>;
  status: ProcessingStatus;
  processing_started_at?: string;
  processing_completed_at?: string;
  processing_duration?: number;
  ocr_text?: string;
  formatted_text?: string;
  display_formatted_text?: string;
  ocr_confidence: number;
  language_detected?: string;
  layout_analysis?: LayoutAnalysis;
  entities?: Entity[];
  extracted_data?: ExtractedData;
  summary?: string;
  ocr_confidence_score: number;
  classification_confidence_score: number;
  layout_confidence_score: number;
  entity_confidence_score: number;
  extraction_confidence_score: number;
  overall_confidence_score: number;
  created_at: string;
  updated_at: string;
}

export enum DocumentType {
  INVOICE = "invoice",
  RECEIPT = "receipt",
  RESUME = "resume",
  PASSPORT = "passport",
  AADHAAR = "aadhaar",
  PAN_CARD = "pan_card",
  DRIVING_LICENSE = "driving_license",
  BANK_STATEMENT = "bank_statement",
  MEDICAL_REPORT = "medical_report",
  CERTIFICATE = "certificate",
  RESEARCH_PAPER = "research_paper",
  UTILITY_BILL = "utility_bill",
  CONTRACT = "contract",
  INSURANCE = "insurance",
  TAX_DOCUMENT = "tax_document",
  OTHER = "other",
}

export enum ProcessingStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
}

export interface LayoutAnalysis {
  headers: LayoutElement[];
  footers: LayoutElement[];
  paragraphs: LayoutElement[];
  tables: TableElement[];
  images: ImageElement[];
  logos: LogoElement[];
  signatures: SignatureElement[];
  qr_codes: QRCodeElement[];
  stamps: StampElement[];
  forms: FormElement[];
  text_blocks: LayoutElement[];
}

export interface LayoutElement {
  bbox: number[][];
  text: string;
  confidence: number;
}

export interface TableElement extends LayoutElement {
  rows?: number;
  columns?: number;
}

export interface ImageElement {
  bbox: number[][];
  confidence: number;
}

export interface LogoElement {
  bbox: number[][];
  confidence: number;
}

export interface SignatureElement {
  bbox: number[][];
  confidence: number;
}

export interface QRCodeElement {
  bbox: number[][];
  data: string;
  confidence: number;
}

export interface StampElement {
  bbox: number[][];
  confidence: number;
  radius?: number;
}

export interface FormElement {
  bbox: number[][];
  type: string;
  confidence: number;
}

export interface Entity {
  text: string;
  label: string;
  start: number;
  end: number;
  confidence: number;
  color?: string;
}

export interface ExtractedData {
  extracted_data: Record<string, any>;
  confidence: number;
  missing_fields: string[];
  warnings: string[];
}

export interface DashboardStats {
  total_documents: number;
  processing_documents: number;
  completed_documents: number;
  failed_documents: number;
  average_confidence: number;
  average_processing_time: number;
  document_type_distribution: Record<string, number>;
  recent_uploads: Document[];
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { documentApi } from '../services/api';
import { Document } from '../types';
import { 
  ArrowLeft, 
  FileText, 
  Download, 
  Copy, 
  CheckCircle,
  XCircle,
  Clock,
  Target,
  Calendar,
  DollarSign,
  Building2,
  Mail,
  Phone,
  MapPin
} from 'lucide-react';

const DocumentView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [doc, setDoc] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'formatted' | 'ocr' | 'extracted'>('overview');
  const [downloading, setDownloading] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<{message: string; type: 'success'|'error'|null} | null>(null);

  useEffect(() => {
    if (id) {
      setDoc(null);
      setLoading(true);
      setToast(null);
      loadDocument(parseInt(id));
    }
  }, [id]);

  const loadDocument = async (docId: number) => {
    try {
      const data = await documentApi.getDocument(docId);
      setDoc(data);
    } catch (error) {
      console.error('Failed to load document:', error);
    } finally {
      setLoading(false);
    }
  };

  const getExportLabel = (format: 'json' | 'csv' | 'txt' | 'pdf' | 'docx' | 'xlsx') => {
    const labels: Record<typeof format, string> = {
      json: 'JSON',
      csv: 'CSV',
      txt: 'TXT',
      pdf: 'PDF',
      docx: 'DOCX',
      xlsx: 'XLSX',
    };
    return labels[format];
  };

  const getExportSuccessMessage = (format: 'json' | 'csv' | 'txt' | 'pdf' | 'docx' | 'xlsx') => {
    const label = getExportLabel(format);
    return `✓ ${label} report downloaded successfully`;
  };

  const handleExport = async (format: 'json' | 'csv' | 'txt' | 'pdf' | 'docx' | 'xlsx') => {
    if (!doc) return;

    const key = format;
    setDownloading((s) => ({ ...s, [key]: true }));

    try {
      const response = await documentApi.downloadExport(doc.id, format);
      const cd = response.headers && (response.headers['content-disposition'] || response.headers['Content-Disposition']);
      const fileExt = format === 'xlsx' ? 'xlsx' : format;
      const cleanName = (doc.original_filename || 'document').replace(/\.[^.]+$/, '');
      let filename = `${cleanName}.${fileExt}`;
      if (typeof cd === 'string') {
        const match = cd.match(/filename\*=UTF-8''(.+)|filename="?([^;\"]+)"?/i);
        if (match) {
          filename = decodeURIComponent(match[1] || match[2] || filename);
        }
      }

      const contentType = typeof response.headers['content-type'] === 'string'
        ? response.headers['content-type']
        : format === 'json'
          ? 'application/json'
          : format === 'csv'
            ? 'text/csv'
            : format === 'txt'
              ? 'text/plain; charset=utf-8'
              : format === 'pdf'
                ? 'application/pdf'
                : format === 'docx'
                  ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                  : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

      const blob = new Blob([response.data], { type: contentType });
      if (blob.size === 0) {
        throw new Error('No file was returned');
      }
      downloadBlob(blob, filename);
      setToast({ message: getExportSuccessMessage(format), type: 'success' });
    } catch (error) {
      console.error('Export failed:', error);
      setToast({ message: '✕ Download failed. Please try again.', type: 'error' });
    } finally {
      setDownloading((s) => ({ ...s, [key]: false }));
    }
  };

  // Helper to download binary responses (pdf/docx/xlsx)
  const handleDownloadFile = async (fmt: 'pdf' | 'docx' | 'xlsx') => {
    await handleExport(fmt);
  };


  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const sanitizeDisplayText = (value: string | null | undefined): string => {
    if (!value) return '';
    return String(value)
      .replace(/\[object Object\]/gi, '')
      .replace(/\bPython object[s]?\b/gi, '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\r/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  };

  const formatExtractedValue = (value: unknown): string => {
    if (value === null || value === undefined) return 'N/A';
    if (typeof value === 'string') {
      const cleaned = sanitizeDisplayText(value);
      return cleaned || 'N/A';
    }
    if (Array.isArray(value)) {
      const items = value.map((item) => formatExtractedValue(item)).filter((item) => item !== 'N/A');
      return items.length ? items.join(', ') : 'N/A';
    }
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value, null, 2);
      } catch {
        return 'N/A';
      }
    }
    return String(value);
  };

  const isHeading = (line: string): boolean => {
    const trimmed = line.trim();
    if (!trimmed) return false;
    if (trimmed.length <= 60 && trimmed === trimmed.toUpperCase()) return true;
    return /^(DOCUMENT|SUMMARY|INVOICE|RECEIPT|CUSTOMER|SELLER|ITEM|TOTAL|PAYMENT|ADDRESS|CONTACT|DETAILS|INFORMATION|PERSONAL|EDUCATION|SKILLS|TABLE|TABLE DATA|FINANCIAL|DATES|REPORT|PROFILE|BILL|HISTORY)/i.test(trimmed);
  };

  const looksLikeTableLine = (line: string): boolean => {
    const trimmed = line.trim();
    if (!trimmed) return false;
    if (trimmed.includes('|')) return trimmed.split('|').filter(Boolean).length >= 2;
    if (/\t/.test(trimmed)) return true;
    return /\s{2,}/.test(trimmed) && trimmed.split(/\s{2,}/).filter(Boolean).length >= 2;
  };

  const renderDocumentPage = (text: string) => {
    const cleanText = sanitizeDisplayText(text);
    if (!cleanText) {
      return <p className="text-gray-600 dark:text-gray-400">No formatted document content available.</p>;
    }

    const lines = cleanText.split(/\n+/).map((line) => line.trim()).filter(Boolean);
    const nodes: React.ReactNode[] = [];
    let tableBuffer: string[] = [];

    const flushTable = () => {
      if (!tableBuffer.length) return;
      const rows = tableBuffer.map((row) => row.includes('|')
        ? row.split('|').map((cell) => cell.trim()).filter((cell) => cell !== '')
        : row.split(/\s{2,}/).map((cell) => cell.trim()).filter(Boolean));
      if (rows.length === 0) {
        tableBuffer = [];
        return;
      }

      const header = rows[0];
      const body = rows.slice(1);
      nodes.push(
        <div className="doc-table-wrap" key={`table-${nodes.length}`}>
          <table className="doc-table">
            {header.length > 0 && (
              <thead>
                <tr>
                  {header.map((cell, idx) => <th key={`h-${idx}`}>{cell}</th>)}
                </tr>
              </thead>
            )}
            {body.length > 0 && (
              <tbody>
                {body.map((row, rowIndex) => (
                  <tr key={`row-${rowIndex}`}>
                    {row.map((cell, cellIndex) => <td key={`c-${rowIndex}-${cellIndex}`}>{cell}</td>)}
                  </tr>
                ))}
              </tbody>
            )}
          </table>
        </div>
      );
      tableBuffer = [];
    };

    lines.forEach((line, index) => {
      if (looksLikeTableLine(line)) {
        tableBuffer.push(line);
        return;
      }

      flushTable();

      if (isHeading(line)) {
        nodes.push(<h3 key={`heading-${index}`} className="document-section-heading">{line}</h3>);
        return;
      }

      if (line.includes(':') && line.split(':').length <= 2) {
        const separatorIndex = line.indexOf(':');
        const label = line.slice(0, separatorIndex).trim();
        const value = line.slice(separatorIndex + 1).trim();
        if (label && value) {
          nodes.push(
            <div key={`kv-${index}`} className="document-keyvalue-row">
              <span className="document-keyvalue-label">{label}</span>
              <span className="document-keyvalue-value">{value}</span>
            </div>
          );
          return;
        }
      }

      nodes.push(<p key={`paragraph-${index}`} className="document-paragraph">{line}</p>);
    });

    flushTable();
    return <div className="formatted-document-shell">{nodes}</div>;
  };


  // Auto-dismiss toast
  React.useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 loading-skeleton w-1/3" />
        <div className="h-96 loading-skeleton" />
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600 dark:text-gray-400">Document not found</p>
      </div>
    );
  }

  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: Target },
    { id: 'formatted' as const, label: 'Formatted View', icon: FileText },
    { id: 'ocr' as const, label: 'Raw OCR Text', icon: FileText },
    { id: 'extracted' as const, label: 'Extracted Data', icon: Building2 },
  ];

  const statusConfig = {
    completed: { icon: CheckCircle, color: 'text-green-600 dark:text-green-400', bg: 'bg-green-100 dark:bg-green-900/30' },
    processing: { icon: Clock, color: 'text-yellow-600 dark:text-yellow-400', bg: 'bg-yellow-100 dark:bg-yellow-900/30' },
    failed: { icon: XCircle, color: 'text-red-600 dark:text-red-400', bg: 'bg-red-100 dark:bg-red-900/30' },
    pending: { icon: Clock, color: 'text-gray-600 dark:text-gray-400', bg: 'bg-gray-100 dark:bg-gray-900/30' },
  };

  const status = doc ? statusConfig[doc.status] || statusConfig.pending : statusConfig.pending;
  const StatusIcon = status.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 rounded-lg hover:bg-white/50 dark:hover:bg-slate-700/50 transition-colors"
          >
            <ArrowLeft className="text-gray-600 dark:text-gray-400" size={24} />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {doc!.original_filename}
            </h1>
            <div className="flex items-center gap-3 mt-1">
              <span className={`text-sm ${status.color} flex items-center gap-1`}>
                <StatusIcon size={16} />
                {doc!.status.toUpperCase()}
              </span>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {doc!.document_type.replace('_', ' ').toUpperCase()}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleExport('json')}
            disabled={!!downloading.json}
            className="glass-button-secondary flex items-center gap-2"
          >
            <Download size={18} />
            {downloading.json ? 'Downloading...' : 'JSON'}
          </button>
          <button
            onClick={() => handleExport('csv')}
            disabled={!!downloading.csv}
            className="glass-button-secondary flex items-center gap-2"
          >
            <Download size={18} />
            {downloading.csv ? 'Downloading...' : 'CSV'}
          </button>
          <button
            onClick={() => handleExport('txt')}
            disabled={!!downloading.txt}
            className="glass-button-secondary flex items-center gap-2"
          >
            <Download size={18} />
            {downloading.txt ? 'Downloading...' : 'TXT'}
          </button>

          <button
            onClick={() => handleDownloadFile('pdf')}
            disabled={!!downloading.pdf}
            className="glass-button-secondary flex items-center gap-2"
          >
            <Download size={18} />
            {downloading.pdf ? 'Downloading...' : 'PDF'}
          </button>

          <button
            onClick={() => handleDownloadFile('docx')}
            disabled={!!downloading.docx}
            className="glass-button-secondary flex items-center gap-2"
          >
            <Download size={18} />
            {downloading.docx ? 'Downloading...' : 'DOCX'}
          </button>

          <button
            onClick={() => handleDownloadFile('xlsx')}
            disabled={!!downloading.xlsx}
            className="glass-button-secondary flex items-center gap-2"
          >
            <Download size={18} />
            {downloading.xlsx ? 'Downloading...' : 'XLSX'}
          </button>
        </div>
      </div>

      {/* Confidence Scores */}
      <div className="glass-card p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          AI Confidence Scores
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[
            { label: 'OCR', value: doc!.ocr_confidence_score },
            { label: 'Classification', value: doc!.classification_confidence_score },
            { label: 'Layout', value: doc!.layout_confidence_score },
            { label: 'Entity', value: doc!.entity_confidence_score },
            { label: 'Extraction', value: doc!.extraction_confidence_score },
            { label: 'Overall', value: doc!.overall_confidence_score },
          ].map((score) => (
            <div key={score.label} className="text-center">
              <div className="relative w-20 h-20 mx-auto mb-2">
                <svg className="w-full h-full transform -rotate-90">
                  <circle
                    cx="40"
                    cy="40"
                    r="36"
                    stroke="currentColor"
                    strokeWidth="8"
                    fill="none"
                    className="text-gray-200 dark:text-slate-700"
                  />
                  <circle
                    cx="40"
                    cy="40"
                    r="36"
                    stroke="currentColor"
                    strokeWidth="8"
                    fill="none"
                    strokeDasharray={`${score.value * 226} 226`}
                    className="text-primary-500 transition-all duration-1000"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-sm font-bold text-gray-900 dark:text-white">
                    {(score.value * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
              <p className="text-xs text-gray-600 dark:text-gray-400">{score.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-primary-500 text-white'
                  : 'bg-white/50 dark:bg-slate-700/50 text-gray-700 dark:text-gray-300 hover:bg-white/70 dark:hover:bg-slate-700/70'
              }`}
            >
              <Icon size={18} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="glass-card p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Summary */}
            {doc!.summary && (
              <div>
                <h4 className="font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                  <FileText size={20} />
                  AI Summary
                </h4>
                <div className="p-4 rounded-lg bg-gray-50 dark:bg-slate-700/50">
                  <p className="text-gray-700 dark:text-gray-300">{doc!.summary}</p>
                </div>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => copyToClipboard(doc!.summary || '')}
                    className="text-sm text-primary-500 hover:text-primary-600 flex items-center gap-1"
                  >
                    <Copy size={16} />
                    Copy
                  </button>
                </div>
              </div>
            )}

            {/* Document Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="font-semibold text-gray-900 dark:text-white mb-3">Document Information</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">File Size</span>
                    <span className="text-gray-900 dark:text-white">
                      {doc!.file_size ? `${(doc!.file_size / 1024 / 1024).toFixed(2)} MB` : 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Type</span>
                    <span className="text-gray-900 dark:text-white">{doc!.mime_type || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Language</span>
                    <span className="text-gray-900 dark:text-white capitalize">
                      {doc!.language_detected || 'Unknown'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Processing Time</span>
                    <span className="text-gray-900 dark:text-white">
                      {doc!.processing_duration ? `${doc!.processing_duration.toFixed(2)}s` : 'N/A'}
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 dark:text-white mb-3">Classification</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Type</span>
                    <span className="text-gray-900 dark:text-white capitalize">
                      {doc!.document_type.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Confidence</span>
                    <span className="text-gray-900 dark:text-white">
                      {(doc!.classification_confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'formatted' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h4 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                <FileText size={20} />
                Formatted View
              </h4>
              <button
                onClick={() => copyToClipboard(sanitizeDisplayText(doc!.display_formatted_text || doc!.formatted_text || doc!.summary || doc!.ocr_text || ''))}
                className="text-sm text-primary-500 hover:text-primary-600 flex items-center gap-1"
              >
                <Copy size={16} />
                Copy
              </button>
            </div>
            {renderDocumentPage(doc!.display_formatted_text || doc!.formatted_text || doc!.summary || doc!.ocr_text || '')}
          </div>
        )}


        {activeTab === 'ocr' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                <FileText size={20} />
                Extracted Text
              </h4>
              <button
                onClick={() => copyToClipboard(doc!.ocr_text || '')}
                className="text-sm text-primary-500 hover:text-primary-600 flex items-center gap-1"
              >
                <Copy size={16} />
                Copy
              </button>
            </div>
            <div className="p-6 rounded-xl bg-white dark:bg-slate-800/80 border border-gray-200 dark:border-slate-700 max-h-[600px] overflow-y-auto shadow-sm">
              <div className="text-base leading-relaxed text-gray-800 dark:text-gray-200 font-sans whitespace-pre-wrap break-words tracking-wide">
                {doc!.ocr_text || 'No text extracted'}
              </div>
            </div>
            <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
              Characters: {doc!.ocr_text?.length || 0} | 
              Confidence: {(doc!.ocr_confidence * 100).toFixed(1)}%
            </div>
          </div>
        )}

        {activeTab === 'extracted' && (
          <div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <Building2 size={20} />
              Extracted Information
            </h4>
            {doc!.extracted_data ? (
              <div className="space-y-4">
                <div className="p-4 rounded-lg bg-gray-50 dark:bg-slate-700/50">
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                    Confidence: {(doc!.extracted_data.confidence * 100).toFixed(1)}%
                  </p>
                </div>
                
                {Object.entries(doc!.extracted_data.extracted_data || {}).map(([key, value]) => (
                  <div key={key} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-slate-700/50">
                    <div className="p-2 rounded-lg bg-primary-100 dark:bg-primary-900/30">
                      {key.toLowerCase().includes('email') && <Mail size={18} className="text-primary-600 dark:text-primary-400" />}
                      {key.toLowerCase().includes('phone') && <Phone size={18} className="text-primary-600 dark:text-primary-400" />}
                      {key.toLowerCase().includes('address') && <MapPin size={18} className="text-primary-600 dark:text-primary-400" />}
                      {key.toLowerCase().includes('date') && <Calendar size={18} className="text-primary-600 dark:text-primary-400" />}
                      {key.toLowerCase().includes('amount') && <DollarSign size={18} className="text-primary-600 dark:text-primary-400" />}
                      {(!key.toLowerCase().includes('email') && 
                        !key.toLowerCase().includes('phone') && 
                        !key.toLowerCase().includes('address') && 
                        !key.toLowerCase().includes('date') && 
                        !key.toLowerCase().includes('amount')) && (
                        <FileText size={18} className="text-primary-600 dark:text-primary-400" />
                      )}
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 dark:text-white capitalize">
                        {key.replace('_', ' ')}
                      </p>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                        {formatExtractedValue(value)}
                      </p>
                    </div>
                  </div>
                ))}

                {doc!.extracted_data.missing_fields && doc!.extracted_data.missing_fields.length > 0 && (
                  <div className="p-4 rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
                    <p className="font-medium text-yellow-900 dark:text-yellow-100 mb-2">
                      Missing Fields
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {doc!.extracted_data.missing_fields.map((field, index) => (
                        <span
                          key={index}
                          className="px-2 py-1 rounded-full bg-yellow-200 dark:bg-yellow-800 text-yellow-800 dark:text-yellow-200 text-sm"
                        >
                          {field}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {doc!.extracted_data.warnings && doc!.extracted_data.warnings.length > 0 && (
                  <div className="p-4 rounded-lg bg-orange-50 dark:bg-orange-900/20">
                    <p className="font-medium text-orange-900 dark:text-orange-100 mb-2">
                      Warnings
                    </p>
                    <ul className="list-disc list-inside text-sm text-orange-800 dark:text-orange-200">
                      {doc!.extracted_data.warnings.map((warning, index) => (
                        <li key={index}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-gray-600 dark:text-gray-400">No extracted data available</p>
            )}
          </div>
        )}
      </div>

      {/* Toast notification */}
      {toast && (
        <div className={`fixed right-6 bottom-6 z-50 max-w-xs shadow-lg rounded-md px-4 py-3 ${toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>
          <div className="flex items-center gap-3">
            <div className="text-xl font-bold">{toast.type === 'success' ? '✓' : '✕'}</div>
            <div className="text-sm">{toast.message}</div>
          </div>
        </div>
      )}

    </motion.div>
  );
};

export default DocumentView;

import axios from 'axios';
import { Document, DashboardStats } from '../types';

const API_BASE_URL = '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const documentApi = {
  uploadDocument: async (file: File): Promise<Document> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post<Document>('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getDocuments: async (skip = 0, limit = 100): Promise<Document[]> => {
    const response = await api.get<Document[]>('/documents', {
      params: { skip, limit },
    });
    return response.data;
  },

  getDocument: async (id: number): Promise<Document> => {
    const response = await api.get<Document>(`/documents/document/${id}`);
    return response.data;
  },

  deleteDocument: async (id: number): Promise<void> => {
    await api.delete(`/documents/document/${id}`);
  },

  classifyDocument: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/documents/classify', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  analyzeLayout: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/documents/layout', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  extractOCR: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/documents/ocr', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  extractInformation: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/documents/extract', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  extractEntities: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/documents/entities', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  generateSummary: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/documents/summary', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getDashboardStats: async (): Promise<DashboardStats> => {
    const response = await api.get<DashboardStats>('/documents/dashboard/stats');
    return response.data;
  },

  downloadExport: async (documentId: number, fmt: 'txt' | 'json' | 'csv' | 'pdf' | 'docx' | 'xlsx') => {
    const response = await api.get(`/export/${fmt}/${documentId}`, { responseType: 'blob' });
    return response;
  },

  exportJSON: async (documentId: number) => {
    const response = await documentApi.downloadExport(documentId, 'json');
    const text = await response.data.text();
    return JSON.parse(text);
  },

  exportCSV: async (documentId: number) => {
    const response = await documentApi.downloadExport(documentId, 'csv');
    return { csv_content: await response.data.text() };
  },

  exportTXT: async (documentId: number) => {
    const response = await documentApi.downloadExport(documentId, 'txt');
    return { txt_content: await response.data.text() };
  },

  downloadFile: async (documentId: number, fmt: string) => {
    return documentApi.downloadExport(documentId, fmt as 'txt' | 'json' | 'csv' | 'pdf' | 'docx' | 'xlsx');
  },

  downloadPdf: async (documentId: number) => {
    return documentApi.downloadExport(documentId, 'pdf');
  },

  downloadDocx: async (documentId: number) => {
    return documentApi.downloadExport(documentId, 'docx');
  },

  downloadXlsx: async (documentId: number) => {
    return documentApi.downloadExport(documentId, 'xlsx');
  },

};

export default api;

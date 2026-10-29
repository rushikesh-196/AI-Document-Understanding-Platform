import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { documentApi } from '../services/api';
import { Document } from '../types';
import { 
  FileText, 
  Search, 
  Filter, 
  Trash2, 
  Calendar,
  Clock,
  CheckCircle,
  XCircle
} from 'lucide-react';

const History: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const data = await documentApi.getDocuments(0, 100);
      setDocuments(data);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this document?')) return;
    
    try {
      await documentApi.deleteDocument(id);
      setDocuments(documents.filter(doc => doc.id !== id));
    } catch (error) {
      console.error('Failed to delete document:', error);
    }
  };

  const filteredDocuments = documents.filter(doc => {
    const matchesSearch = 
      doc.original_filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.ocr_text?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesType = filterType === 'all' || doc.document_type === filterType;
    const matchesStatus = filterStatus === 'all' || doc.status === filterStatus;
    
    return matchesSearch && matchesType && matchesStatus;
  });

  const documentTypes = ['all', ...Array.from(new Set(documents.map(doc => doc.document_type)))];
  const statuses = ['all', 'pending', 'processing', 'completed', 'failed'];

  const statusConfig = {
    completed: { icon: CheckCircle, color: 'text-green-600 dark:text-green-400', bg: 'bg-green-100 dark:bg-green-900/30' },
    processing: { icon: Clock, color: 'text-yellow-600 dark:text-yellow-400', bg: 'bg-yellow-100 dark:bg-yellow-900/30' },
    failed: { icon: XCircle, color: 'text-red-600 dark:text-red-400', bg: 'bg-red-100 dark:bg-red-900/30' },
    pending: { icon: Clock, color: 'text-gray-600 dark:text-gray-400', bg: 'bg-gray-100 dark:bg-gray-900/30' },
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 loading-skeleton w-1/3" />
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-24 loading-skeleton" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Document History
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          View and manage your processed documents
        </p>
      </div>

      {/* Filters */}
      <div className="glass-card p-4">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
            <input
              type="text"
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="glass-input w-full pl-10"
            />
          </div>

          {/* Type Filter */}
          <div className="flex items-center gap-2">
            <Filter size={20} className="text-gray-400" />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="glass-input"
            >
              {documentTypes.map(type => (
                <option key={type} value={type}>
                  {type.replace('_', ' ').toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="glass-input"
          >
            {statuses.map(status => (
              <option key={status} value={status}>
                {status.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Documents List */}
      {filteredDocuments.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <FileText className="mx-auto text-gray-400 mb-4" size={48} />
          <p className="text-gray-600 dark:text-gray-400">
            {searchQuery || filterType !== 'all' || filterStatus !== 'all'
              ? 'No documents match your filters'
              : 'No documents processed yet'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredDocuments.map((doc, index) => {
            const status = statusConfig[doc.status] || statusConfig.pending;
            const StatusIcon = status.icon;

            return (
              <motion.div
                key={doc.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                className="glass-card p-4 hover:scale-[1.01] transition-transform"
              >
                <div className="flex items-center justify-between">
                  <Link
                    to={`/document/${doc.id}`}
                    className="flex items-center gap-4 flex-1"
                  >
                    <div className={`p-3 rounded-xl ${status.bg}`}>
                      <StatusIcon className={status.color} size={24} />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 dark:text-white">
                        {doc.original_filename}
                      </p>
                      <div className="flex items-center gap-4 mt-1 text-sm text-gray-600 dark:text-gray-400">
                        <span className="capitalize">{doc.document_type.replace('_', ' ')}</span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <Calendar size={14} />
                          {new Date(doc.created_at).toLocaleDateString()}
                        </span>
                        {doc.processing_duration && (
                          <>
                            <span>•</span>
                            <span className="flex items-center gap-1">
                              <Clock size={14} />
                              {doc.processing_duration.toFixed(2)}s
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </Link>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {(doc.overall_confidence_score * 100).toFixed(0)}%
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400">Confidence</p>
                    </div>
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="p-2 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 transition-colors"
                    >
                      <Trash2 size={20} />
                    </button>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {documents.length}
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">Total</p>
        </div>
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-green-600 dark:text-green-400">
            {documents.filter(d => d.status === 'completed').length}
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">Completed</p>
        </div>
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
            {documents.filter(d => d.status === 'processing').length}
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">Processing</p>
        </div>
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-red-600 dark:text-red-400">
            {documents.filter(d => d.status === 'failed').length}
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">Failed</p>
        </div>
      </div>
    </motion.div>
  );
};

export default History;

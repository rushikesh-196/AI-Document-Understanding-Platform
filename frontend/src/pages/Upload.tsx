import React, { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { documentApi } from '../services/api';
import { Upload as UploadIcon, FileText, X, CheckCircle, AlertCircle } from 'lucide-react';

const Upload: React.FC = () => {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setUploadedFile(acceptedFiles[0]);
      setError(null);
      setSuccess(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/tiff': ['.tiff'],
    },
    maxFiles: 1,
    maxSize: 16 * 1024 * 1024, // 16MB
  });

  const handleUpload = async () => {
    if (!uploadedFile) return;

    setUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 200);

      const result = await documentApi.uploadDocument(uploadedFile);
      
      clearInterval(progressInterval);
      setUploadProgress(100);
      setSuccess(true);

      setTimeout(() => {
        navigate(`/document/${result.id}`);
      }, 1500);
    } catch (err) {
      setError('Failed to upload document. Please try again.');
      setUploadProgress(0);
    } finally {
      setUploading(false);
    }
  };

  const removeFile = () => {
    setUploadedFile(null);
    setError(null);
    setSuccess(false);
    setUploadProgress(0);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="max-w-4xl mx-auto"
    >
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Upload Document
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Upload your documents for AI-powered analysis
        </p>
      </div>

      <div className="glass-card p-8">
        {/* Upload Zone */}
        {!uploadedFile ? (
          <div
            {...getRootProps()}
            className={`upload-zone ${isDragActive ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20' : ''}`}
          >
            <input {...getInputProps()} />
            <div className="flex flex-col items-center">
              <div className={`p-4 rounded-full mb-4 ${isDragActive ? 'bg-primary-500' : 'bg-gray-200 dark:bg-slate-700'}`}>
                <UploadIcon 
                  size={32} 
                  className={isDragActive ? 'text-white' : 'text-gray-600 dark:text-gray-400'} 
                />
              </div>
              <p className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                {isDragActive ? 'Drop your document here' : 'Drag & drop your document here'}
              </p>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                or click to browse
              </p>
              <div className="flex gap-2 text-sm text-gray-500 dark:text-gray-500">
                <span className="px-3 py-1 rounded-full bg-gray-100 dark:bg-slate-700">PDF</span>
                <span className="px-3 py-1 rounded-full bg-gray-100 dark:bg-slate-700">JPG</span>
                <span className="px-3 py-1 rounded-full bg-gray-100 dark:bg-slate-700">PNG</span>
                <span className="px-3 py-1 rounded-full bg-gray-100 dark:bg-slate-700">TIFF</span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-500 mt-4">
                Maximum file size: 16MB
              </p>
            </div>
          </div>
        ) : (
          /* File Preview */
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-slate-700/50">
              <div className="flex items-center gap-4">
                <div className="p-2 rounded-lg bg-primary-100 dark:bg-primary-900/30">
                  <FileText className="text-primary-600 dark:text-primary-400" size={24} />
                </div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">
                    {uploadedFile.name}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {(uploadedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              </div>
              {!uploading && !success && (
                <button
                  onClick={removeFile}
                  className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-slate-600 transition-colors"
                >
                  <X className="text-gray-600 dark:text-gray-400" size={20} />
                </button>
              )}
            </div>

            {/* Upload Progress */}
            {uploading && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Uploading...</span>
                  <span className="font-medium text-gray-900 dark:text-white">
                    {uploadProgress}%
                  </span>
                </div>
                <div className="confidence-bar">
                  <div
                    className="confidence-fill bg-gradient-to-r from-primary-500 to-primary-600"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Success State */}
            {success && (
              <div className="flex items-center gap-3 p-4 rounded-lg bg-green-50 dark:bg-green-900/20">
                <CheckCircle className="text-green-600 dark:text-green-400" size={24} />
                <div>
                  <p className="font-medium text-green-900 dark:text-green-100">
                    Upload successful!
                  </p>
                  <p className="text-sm text-green-700 dark:text-green-300">
                    Redirecting to document view...
                  </p>
                </div>
              </div>
            )}

            {/* Error State */}
            {error && (
              <div className="flex items-center gap-3 p-4 rounded-lg bg-red-50 dark:bg-red-900/20">
                <AlertCircle className="text-red-600 dark:text-red-400" size={24} />
                <p className="text-red-900 dark:text-red-100">{error}</p>
              </div>
            )}

            {/* Upload Button */}
            {!uploading && !success && (
              <button
                onClick={handleUpload}
                className="glass-button w-full flex items-center justify-center gap-2"
              >
                <UploadIcon size={20} />
                Upload & Process
              </button>
            )}
          </div>
        )}

        {/* Info Section */}
        <div className="mt-8 pt-6 border-t border-gray-200 dark:border-slate-700">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-3">
            What happens next?
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex-shrink-0">
                <span className="text-blue-600 dark:text-blue-400 font-bold">1</span>
              </div>
              <div>
                <p className="font-medium text-gray-900 dark:text-white">OCR Analysis</p>
                <p className="text-gray-600 dark:text-gray-400">Extract text from document</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-green-100 dark:bg-green-900/30 flex-shrink-0">
                <span className="text-green-600 dark:text-green-400 font-bold">2</span>
              </div>
              <div>
                <p className="font-medium text-gray-900 dark:text-white">AI Processing</p>
                <p className="text-gray-600 dark:text-gray-400">Classify and extract information</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex-shrink-0">
                <span className="text-purple-600 dark:text-purple-400 font-bold">3</span>
              </div>
              <div>
                <p className="font-medium text-gray-900 dark:text-white">Results</p>
                <p className="text-gray-600 dark:text-gray-400">View extracted data and summary</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default Upload;

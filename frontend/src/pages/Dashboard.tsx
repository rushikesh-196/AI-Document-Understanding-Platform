import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { documentApi } from '../services/api';
import { DashboardStats } from '../types';
import { 
  FileText, 
  Clock, 
  CheckCircle, 
  XCircle, 
  TrendingUp,
  Upload,
  ArrowRight
} from 'lucide-react';
import { Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const data = await documentApi.getDashboardStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 loading-skeleton w-1/3" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-32 loading-skeleton" />
          ))}
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600 dark:text-gray-400">Failed to load dashboard statistics</p>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Total Documents',
      value: stats.total_documents,
      icon: FileText,
      color: 'from-blue-500 to-blue-600',
    },
    {
      title: 'Processing',
      value: stats.processing_documents,
      icon: Clock,
      color: 'from-yellow-500 to-yellow-600',
    },
    {
      title: 'Completed',
      value: stats.completed_documents,
      icon: CheckCircle,
      color: 'from-green-500 to-green-600',
    },
    {
      title: 'Failed',
      value: stats.failed_documents,
      icon: XCircle,
      color: 'from-red-500 to-red-600',
    },
  ];

  const documentTypeData = Object.entries(stats.document_type_distribution).map(([name, value]) => ({
    name: name.replace('_', ' ').toUpperCase(),
    value,
  }));

  const COLORS = ['#0ea5e9', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Overview of your document processing
          </p>
        </div>
        <Link to="/upload">
          <button className="glass-button flex items-center gap-2">
            <Upload size={20} />
            Upload Document
          </button>
        </Link>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((card, index) => {
          const Icon = card.icon;
          return (
            <motion.div
              key={card.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="stat-card"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-gray-600 dark:text-gray-400 text-sm font-medium">
                    {card.title}
                  </p>
                  <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                    {card.value}
                  </p>
                </div>
                <div className={`p-3 rounded-xl bg-gradient-to-br ${card.color}`}>
                  <Icon className="text-white" size={24} />
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Type Distribution */}
        <div className="glass-card p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Document Type Distribution
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={documentTypeData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {documentTypeData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Performance Metrics */}
        <div className="glass-card p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Performance Metrics
          </h3>
          <div className="space-y-6">
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-gray-600 dark:text-gray-400">Average Confidence</span>
                <span className="font-semibold text-gray-900 dark:text-white">
                  {(stats.average_confidence * 100).toFixed(1)}%
                </span>
              </div>
              <div className="confidence-bar">
                <div
                  className="confidence-fill bg-gradient-to-r from-green-500 to-green-600"
                  style={{ width: `${stats.average_confidence * 100}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-2">
                <span className="text-gray-600 dark:text-gray-400">Avg Processing Time</span>
                <span className="font-semibold text-gray-900 dark:text-white">
                  {stats.average_processing_time.toFixed(2)}s
                </span>
              </div>
              <div className="confidence-bar">
                <div
                  className="confidence-fill bg-gradient-to-r from-blue-500 to-blue-600"
                  style={{ width: `${Math.min((stats.average_processing_time / 10) * 100, 100)}%` }}
                />
              </div>
            </div>

            <div className="pt-4 border-t border-gray-200 dark:border-slate-700">
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <TrendingUp size={20} />
                <span className="font-medium">
                  {stats.completed_documents > 0 
                    ? `Success Rate: ${((stats.completed_documents / stats.total_documents) * 100).toFixed(1)}%`
                    : 'No documents processed yet'
                  }
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Uploads */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Recent Uploads
          </h3>
          <Link to="/history" className="text-primary-500 hover:text-primary-600 flex items-center gap-1">
            View All <ArrowRight size={16} />
          </Link>
        </div>

        {stats.recent_uploads.length === 0 ? (
          <div className="text-center py-8 text-gray-600 dark:text-gray-400">
            No documents uploaded yet
          </div>
        ) : (
          <div className="space-y-3">
            {stats.recent_uploads.map((doc) => (
              <Link
                key={doc.id}
                to={`/document/${doc.id}`}
                className="flex items-center justify-between p-4 rounded-lg hover:bg-white/50 dark:hover:bg-slate-700/50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className="p-2 rounded-lg bg-primary-100 dark:bg-primary-900/30">
                    <FileText className="text-primary-600 dark:text-primary-400" size={20} />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {doc.original_filename}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {doc.document_type.replace('_', ' ').toUpperCase()}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-medium ${
                    doc.status === 'completed' ? 'text-green-600 dark:text-green-400' :
                    doc.status === 'processing' ? 'text-yellow-600 dark:text-yellow-400' :
                    doc.status === 'failed' ? 'text-red-600 dark:text-red-400' :
                    'text-gray-600 dark:text-gray-400'
                  }`}>
                    {doc.status.toUpperCase()}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {(doc.overall_confidence_score * 100).toFixed(0)}% confidence
                  </p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default Dashboard;

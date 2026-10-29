import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTheme } from '../../context/ThemeContext';
import { 
  LayoutDashboard, 
  Upload, 
  FileText, 
  History, 
  Moon, 
  Sun,
  Menu,
  X
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { isDark, toggleTheme } = useTheme();
  const location = useLocation();
  const [isSidebarOpen, setIsSidebarOpen] = React.useState(true);

  const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/upload', label: 'Upload', icon: Upload },
    { path: '/history', label: 'History', icon: History },
  ];

  return (
    <div className={`min-h-screen ${isDark ? 'dark' : ''}`}>
      <div className="flex min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-slate-900 dark:to-slate-800">
        {/* Sidebar */}
        <AnimatePresence>
          {isSidebarOpen && (
            <motion.aside
              initial={{ x: -300 }}
              animate={{ x: 0 }}
              exit={{ x: -300 }}
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="fixed left-0 top-0 h-full w-64 glass-card border-r border-white/20 dark:border-slate-700/20 z-50"
            >
              <div className="p-6">
                <h1 className="text-2xl font-bold bg-gradient-to-r from-primary-500 to-primary-600 bg-clip-text text-transparent">
                  DocAI
                </h1>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Document Intelligence
                </p>
              </div>

              <nav className="mt-6 px-4">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.path;
                  
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`sidebar-item mb-2 ${isActive ? 'sidebar-item-active' : 'text-gray-700 dark:text-gray-300'}`}
                    >
                      <Icon size={20} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </nav>

              <div className="absolute bottom-0 left-0 right-0 p-4">
                <button
                  onClick={toggleTheme}
                  className="sidebar-item w-full"
                >
                  {isDark ? <Sun size={20} /> : <Moon size={20} />}
                  <span>{isDark ? 'Light Mode' : 'Dark Mode'}</span>
                </button>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        {/* Main Content */}
        <div className={`flex-1 transition-all duration-300 ${isSidebarOpen ? 'ml-64' : 'ml-0'}`}>
          {/* Header */}
          <header className="glass-card border-b border-white/20 dark:border-slate-700/20 sticky top-0 z-40">
            <div className="flex items-center justify-between px-6 py-4">
              <button
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                className="p-2 rounded-lg hover:bg-white/50 dark:hover:bg-slate-700/50 transition-colors"
              >
                {isSidebarOpen ? <X size={24} /> : <Menu size={24} />}
              </button>

              <div className="flex items-center gap-4">
                <div className="glass-input flex items-center gap-2">
                  <FileText size={18} className="text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search documents..."
                    className="bg-transparent border-none outline-none w-64"
                  />
                </div>
              </div>
            </div>
          </header>

          {/* Page Content */}
          <main className="p-6">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
};

export default Layout;

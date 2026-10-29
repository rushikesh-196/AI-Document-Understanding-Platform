import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import Layout from './components/Shared/Layout';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import DocumentView from './pages/DocumentView';
import History from './pages/History';
import './index.css';

function App() {
  return (
    <ThemeProvider>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/document/:id" element={<DocumentView />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </Layout>
      </Router>
    </ThemeProvider>
  );
}

export default App;

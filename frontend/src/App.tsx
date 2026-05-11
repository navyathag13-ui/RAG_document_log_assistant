import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/layout/Layout'
import DashboardPage from './pages/DashboardPage'
import UploadPage from './pages/UploadPage'
import DocumentsPage from './pages/DocumentsPage'
import SearchPage from './pages/SearchPage'
import AskPage from './pages/AskPage'
import ComparePromptsPage from './pages/ComparePromptsPage'
import EvaluationPage from './pages/EvaluationPage'
import ExperimentsPage from './pages/ExperimentsPage'

export default function App() {
  return (
    <Layout>
      <Routes>
        {/* ── v1 routes ─────────────────────────────── */}
        <Route path="/"          element={<DashboardPage />}      />
        <Route path="/upload"    element={<UploadPage />}         />
        <Route path="/documents" element={<DocumentsPage />}      />
        <Route path="/search"    element={<SearchPage />}         />
        <Route path="/ask"       element={<AskPage />}            />
        {/* ── v2 routes ─────────────────────────────── */}
        <Route path="/compare"     element={<ComparePromptsPage />} />
        <Route path="/evaluation"  element={<EvaluationPage />}    />
        <Route path="/experiments" element={<ExperimentsPage />}   />
        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

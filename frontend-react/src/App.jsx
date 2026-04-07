import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';

// Pages
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardLayout from './pages/dashboard/DashboardLayout';
import DashboardHome from './pages/dashboard/DashboardHome';
import ProjectsPage from './pages/dashboard/ProjectsPage';
import ProjectDetail from './pages/dashboard/ProjectDetail';
import ProjectResults from './pages/dashboard/ProjectResults';
import ProjectExport from './pages/dashboard/ProjectExport';
import ProjectHistory from './pages/dashboard/ProjectHistory';
import SettingsPage from './pages/dashboard/SettingsPage';

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#0f172a' }}>
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-slate-400 text-sm">로딩 중...</span>
      </div>
    </div>
  );
  return user ? children : <Navigate to="/login" replace />;
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  return user ? <Navigate to="/dashboard" replace /> : children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: '#1e293b',
              color: '#f1f5f9',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '10px',
              fontSize: '14px',
            },
            success: { iconTheme: { primary: '#10b981', secondary: '#fff' } },
            error: { iconTheme: { primary: '#ef4444', secondary: '#fff' } },
          }}
        />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
          <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
          <Route path="/dashboard" element={<PrivateRoute><DashboardLayout /></PrivateRoute>}>
            <Route index element={<DashboardHome />} />
          </Route>
          <Route path="/projects" element={<PrivateRoute><DashboardLayout /></PrivateRoute>}>
            <Route index element={<ProjectsPage />} />
            <Route path=":id" element={<ProjectDetail />} />
            <Route path=":id/results" element={<ProjectResults />} />
            <Route path=":id/export" element={<ProjectExport />} />
            <Route path=":id/history" element={<ProjectHistory />} />
          </Route>
          <Route path="/settings" element={<PrivateRoute><DashboardLayout /></PrivateRoute>}>
            <Route index element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

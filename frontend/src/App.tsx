import { NavLink, Route, Routes } from 'react-router-dom';

import { AuthProvider, useAuth } from './contexts/AuthContext';
import CorrelationsPage from './pages/CorrelationsPage';
import NewsPage from './pages/NewsPage';
import LoginPage from './pages/LoginPage';
import PremiumPage from './pages/PremiumPage';
import RulesPage from './pages/RulesPage';
import ProtectedRoute from './components/ProtectedRoute';

function AppContent() {
  const { isAuthenticated, isAdmin, logout } = useAuth();

  return (
    <div className="app-shell">
      <div className="glow glow-left" />
      <div className="glow glow-right" />

      <header className="top-nav">
        <div className="nav-brand">
          <span className="nav-pill">TFG Finance</span>
          <span className="nav-title">Motor analítico</span>
        </div>
        <nav className="nav-links">
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : undefined)}>
            Correlaciones
          </NavLink>
          <NavLink to="/news" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            Noticias
          </NavLink>
          <NavLink to="/rules" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            Reglas
          </NavLink>
          {isAdmin && (
            <NavLink to="/premium" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              Admin Panel
            </NavLink>
          )}
          {isAuthenticated ? (
            <button onClick={logout} className="ghost" style={{ padding: '10px 14px' }}>
              Salir
            </button>
          ) : (
            <NavLink to="/login" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              Login
            </NavLink>
          )}
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<CorrelationsPage />} />
        <Route path="/news" element={<NewsPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/rules" element={<RulesPage />} />
        <Route
          path="/premium"
          element={
            <ProtectedRoute>
              <PremiumPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

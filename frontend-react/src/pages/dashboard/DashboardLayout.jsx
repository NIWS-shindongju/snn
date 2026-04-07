import { useState } from 'react';
import { Outlet, NavLink, useNavigate, Link } from 'react-router-dom';
import {
  Leaf, LayoutDashboard, FolderOpen, Settings, LogOut,
  Bell, ChevronDown, Menu, X, User, Shield, BarChart3
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: '대시보드', exact: true },
  { to: '/projects', icon: FolderOpen, label: '프로젝트' },
  { to: '/settings', icon: Settings, label: '설정' },
];

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-5 border-b border-white/5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-sky-500 flex items-center justify-center flex-shrink-0">
          <Leaf className="w-4 h-4 text-white" />
        </div>
        <div>
          <span className="font-bold text-white text-sm">TraceCheck</span>
          <div className="text-xs text-slate-500">ESG Platform</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="text-xs font-semibold text-slate-600 uppercase tracking-widest px-3 mb-3">메뉴</div>
        {navItems.map(({ to, icon: Icon, label, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              `sidebar-item ${isActive ? 'active' : ''}`
            }
            onClick={() => setSidebarOpen(false)}
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User info */}
      <div className="px-3 pb-4 border-t border-white/5 pt-4">
        <div className="glass rounded-xl p-3">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500 to-sky-500 flex items-center justify-center flex-shrink-0">
              <span className="text-white text-xs font-bold">
                {user?.email?.[0]?.toUpperCase() || 'U'}
              </span>
            </div>
            <div className="min-w-0">
              <div className="text-white text-xs font-medium truncate">{user?.email || '사용자'}</div>
              <div className="text-slate-500 text-xs truncate">{user?.role === 'admin' ? '관리자' : '멤버'}</div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 w-full text-slate-500 hover:text-red-400 text-xs py-1.5 px-2 rounded-lg hover:bg-red-500/10 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            로그아웃
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex" style={{ background: '#0f172a' }}>
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-56 flex-col border-r border-white/5 flex-shrink-0"
        style={{ background: '#0a1628' }}>
        <SidebarContent />
      </aside>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <aside className="relative w-56 flex flex-col border-r border-white/5 z-10" style={{ background: '#0a1628' }}>
            <button
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="w-5 h-5" />
            </button>
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-14 flex items-center justify-between px-4 sm:px-6 border-b border-white/5 flex-shrink-0"
          style={{ background: 'rgba(10,22,40,0.8)', backdropFilter: 'blur(12px)' }}>
          <div className="flex items-center gap-3">
            <button
              className="lg:hidden text-slate-400 hover:text-white transition-colors"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="hidden sm:flex items-center gap-1 text-sm text-slate-500">
              <span className="text-slate-600">TraceCheck</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Notification Bell */}
            <button className="relative w-9 h-9 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/5 transition-all">
              <Bell className="w-4 h-4" />
              <div className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-emerald-500" />
            </button>

            {/* User menu */}
            <div className="relative">
              <button
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
              >
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-emerald-500 to-sky-500 flex items-center justify-center">
                  <span className="text-white text-xs font-bold">
                    {user?.email?.[0]?.toUpperCase() || 'U'}
                  </span>
                </div>
                <span className="hidden sm:block text-sm text-slate-300 max-w-[120px] truncate">{user?.email || '사용자'}</span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 top-full mt-2 w-48 rounded-xl border border-white/10 py-1 z-50"
                  style={{ background: '#1e293b' }}
                  onBlur={() => setUserMenuOpen(false)}>
                  <div className="px-3 py-2 border-b border-white/5">
                    <div className="text-xs text-slate-400 truncate">{user?.email}</div>
                    <div className="text-xs text-slate-600">{user?.org_name || '조직'}</div>
                  </div>
                  <Link
                    to="/settings"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
                    onClick={() => setUserMenuOpen(false)}
                  >
                    <Settings className="w-3.5 h-3.5" />
                    설정
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    로그아웃
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <div className="page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  FolderOpen, MapPin, AlertTriangle, TrendingUp, ArrowRight,
  Clock, CheckCircle, Loader, XCircle, BarChart3, Activity,
  Plus
} from 'lucide-react';
import { projectsAPI, analysisAPI } from '../../api/client';
import { useAuth } from '../../context/AuthContext';

function StatCard({ icon, label, value, sub, color, bg }) {
  return (
    <div className="stat-card">
      <div className="flex items-start justify-between mb-4">
        <div className={`w-10 h-10 rounded-xl ${bg} ${color} flex items-center justify-center`}>
          {icon}
        </div>
        <TrendingUp className="w-4 h-4 text-slate-600" />
      </div>
      <div className="text-2xl font-bold text-white mb-1">{value}</div>
      <div className="text-slate-400 text-sm">{label}</div>
      {sub && <div className="text-xs text-slate-600 mt-1">{sub}</div>}
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    completed: { label: '완료', color: 'text-emerald-400', bg: 'bg-emerald-500/10', icon: <CheckCircle className="w-3 h-3" /> },
    running: { label: '실행 중', color: 'text-sky-400', bg: 'bg-sky-500/10', icon: <Loader className="w-3 h-3 animate-spin" /> },
    failed: { label: '실패', color: 'text-red-400', bg: 'bg-red-500/10', icon: <XCircle className="w-3 h-3" /> },
    pending: { label: '대기', color: 'text-amber-400', bg: 'bg-amber-500/10', icon: <Clock className="w-3 h-3" /> },
  };
  const s = map[status] || map.pending;
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-medium ${s.color} ${s.bg}`}>
      {s.icon}{s.label}
    </span>
  );
}

export default function DashboardHome() {
  const { user } = useAuth();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    projectsAPI.list()
      .then(r => setProjects(r.data || []))
      .catch(() => setProjects([]))
      .finally(() => setLoading(false));
  }, []);

  const totalProjects = projects.length;
  const totalPlots = projects.reduce((a, p) => a + (p.plot_count || 0), 0);
  const highRisk = projects.reduce((a, p) => a + (p.high_risk_count || 0), 0);
  const recentProjects = [...projects].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 5);

  const greetHour = new Date().getHours();
  const greeting = greetHour < 12 ? '좋은 아침이에요' : greetHour < 18 ? '안녕하세요' : '수고하셨어요';

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">
            {greeting}, {user?.email?.split('@')[0] || '사용자'} 님 👋
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            오늘의 공급망 ESG 현황을 확인하세요.
          </p>
        </div>
        <Link to="/projects" className="btn-primary px-5 py-2.5 rounded-xl text-sm">
          <Plus className="w-4 h-4" />
          새 프로젝트
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<FolderOpen className="w-5 h-5" />}
          label="총 프로젝트"
          value={loading ? '—' : totalProjects}
          sub="활성 공급망 프로젝트"
          color="text-sky-400"
          bg="bg-sky-500/10"
        />
        <StatCard
          icon={<MapPin className="w-5 h-5" />}
          label="총 필지 수"
          value={loading ? '—' : totalPlots.toLocaleString()}
          sub="분석된 농장·필지"
          color="text-emerald-400"
          bg="bg-emerald-500/10"
        />
        <StatCard
          icon={<AlertTriangle className="w-5 h-5" />}
          label="HIGH 위험"
          value={loading ? '—' : highRisk}
          sub="즉각 검토 필요"
          color="text-red-400"
          bg="bg-red-500/10"
        />
        <StatCard
          icon={<BarChart3 className="w-5 h-5" />}
          label="분석 완료율"
          value={loading ? '—' : totalProjects > 0 ? `${Math.round((projects.filter(p => p.status === 'done' || p.status === 'completed').length / totalProjects) * 100)}%` : '—'}
          sub="최근 30일 기준"
          color="text-purple-400"
          bg="bg-purple-500/10"
        />
      </div>

      {/* Content Grid */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Recent Projects */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              최근 프로젝트
            </h2>
            <Link to="/projects" className="text-sm text-emerald-400 hover:text-emerald-300 flex items-center gap-1 transition-colors">
              전체 보기 <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="glass rounded-2xl overflow-hidden">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-8 h-8 spinner" />
              </div>
            ) : recentProjects.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center px-4">
                <FolderOpen className="w-12 h-12 text-slate-600 mb-3" />
                <div className="text-slate-400 font-medium mb-1">프로젝트가 없습니다</div>
                <div className="text-slate-600 text-sm mb-4">첫 번째 공급망 프로젝트를 만들어보세요.</div>
                <Link to="/projects" className="btn-primary text-sm px-5 py-2 rounded-xl">
                  <Plus className="w-4 h-4" /> 프로젝트 만들기
                </Link>
              </div>
            ) : (
              <table className="data-table w-full">
                <thead>
                  <tr>
                    <th>프로젝트</th>
                    <th>필지 수</th>
                    <th>HIGH 위험</th>
                    <th>상태</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {recentProjects.map(p => (
                    <tr key={p.id}>
                      <td>
                        <div className="font-medium text-white">{p.name}</div>
                        <div className="text-xs text-slate-500 mt-0.5">{p.description || '설명 없음'}</div>
                      </td>
                      <td className="text-slate-300">{(p.plot_count || 0).toLocaleString()}</td>
                      <td>
                        {(p.high_risk_count || 0) > 0 ? (
                          <span className="badge-high text-xs px-2 py-0.5 rounded-full">{p.high_risk_count}</span>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td><StatusBadge status={p.status || 'pending'} /></td>
                      <td>
                        <Link to={`/projects/${p.id}`} className="text-sky-400 hover:text-sky-300 transition-colors">
                          <ArrowRight className="w-4 h-4" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Quick Actions + Info */}
        <div className="space-y-4">
          <div>
            <h2 className="font-semibold text-white flex items-center gap-2 mb-4">
              <CheckCircle className="w-4 h-4 text-sky-400" />
              빠른 시작
            </h2>
            <div className="space-y-3">
              {[
                { icon: <Plus className="w-4 h-4" />, label: '새 프로젝트', to: '/projects', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
                { icon: <FolderOpen className="w-4 h-4" />, label: '프로젝트 목록', to: '/projects', color: 'text-sky-400', bg: 'bg-sky-500/10' },
                { icon: <BarChart3 className="w-4 h-4" />, label: '분석 결과', to: '/projects', color: 'text-purple-400', bg: 'bg-purple-500/10' },
              ].map((a, i) => (
                <Link key={i} to={a.to} className="flex items-center gap-3 glass rounded-xl p-3 hover:bg-white/5 transition-colors group">
                  <div className={`w-8 h-8 rounded-lg ${a.bg} ${a.color} flex items-center justify-center`}>{a.icon}</div>
                  <span className="text-slate-300 text-sm group-hover:text-white transition-colors">{a.label}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-600 ml-auto group-hover:text-slate-400 transition-colors" />
                </Link>
              ))}
            </div>
          </div>

          {/* EUDR info */}
          <div className="glass rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span className="text-sm font-semibold text-white">EUDR 규정 정보</span>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">적용 기준일</span>
                <span className="text-white font-medium">2020.12.31</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">시행일</span>
                <span className="text-amber-400 font-medium">2025.12.30</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">대상 품목</span>
                <span className="text-white font-medium">7개 원자재</span>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-white/5">
              <a href="https://environment.ec.europa.eu/topics/forests/deforestation/regulation-deforestation-free-products_en"
                target="_blank" rel="noopener noreferrer"
                className="text-xs text-sky-400 hover:text-sky-300 flex items-center gap-1 transition-colors">
                공식 규정 확인 <ArrowRight className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

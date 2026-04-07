import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  FolderOpen, Plus, Search, AlertTriangle, MapPin,
  Calendar, Trash2, ArrowRight, Loader, CheckCircle,
  XCircle, Clock, MoreVertical, X
} from 'lucide-react';
import { projectsAPI, analysisAPI } from '../../api/client';
import toast from 'react-hot-toast';

function StatusBadge({ status }) {
  const map = {
    completed: { label: '완료', cls: 'badge-low' },
    done: { label: '완료', cls: 'badge-low' },
    running: { label: '실행 중', cls: 'badge-review' },
    failed: { label: '실패', cls: 'badge-high' },
    pending: { label: '대기', cls: 'badge-review' },
    created: { label: '생성됨', cls: 'badge-low' },
  };
  const s = map[status] || map.created;
  return <span className={s.cls}>{s.label}</span>;
}

function CreateProjectModal({ onClose, onCreated }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) { toast.error('프로젝트 이름을 입력하세요.'); return; }
    setLoading(true);
    try {
      const r = await projectsAPI.create({ name: name.trim(), description: description.trim() });
      toast.success('프로젝트가 생성되었습니다!');
      onCreated(r.data);
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || '프로젝트 생성에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-content">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-white">새 프로젝트 생성</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">프로젝트 이름 *</label>
            <input
              type="text"
              className="form-input"
              placeholder="예: 브라질 콩 공급망 2025"
              value={name}
              onChange={e => setName(e.target.value)}
              autoFocus
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">설명 (선택)</label>
            <textarea
              className="form-input resize-none"
              rows={3}
              placeholder="프로젝트 목적이나 범위를 간략히 설명하세요."
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1 justify-center py-2.5 rounded-xl">
              취소
            </button>
            <button type="submit" disabled={loading} className="btn-primary flex-1 justify-center py-2.5 rounded-xl disabled:opacity-50">
              {loading ? <><div className="w-4 h-4 spinner" />생성 중...</> : <>생성하기</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ProjectCard({ project, onDelete }) {
  const [menuOpen, setMenuOpen] = useState(false);

  const statusIcon = {
    completed: <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />,
    done: <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />,
    running: <Loader className="w-3.5 h-3.5 text-sky-400 animate-spin" />,
    failed: <XCircle className="w-3.5 h-3.5 text-red-400" />,
  }[project.status] || <Clock className="w-3.5 h-3.5 text-amber-400" />;

  return (
    <div className="glass rounded-2xl p-5 card-hover relative">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-sky-500/20 border border-emerald-500/20 flex items-center justify-center">
          <FolderOpen className="w-5 h-5 text-emerald-400" />
        </div>
        <div className="relative">
          <button
            className="text-slate-500 hover:text-slate-300 transition-colors p-1"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            <MoreVertical className="w-4 h-4" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 w-36 rounded-xl border border-white/10 py-1 z-10"
              style={{ background: '#1e293b' }}>
              <button
                onClick={() => { setMenuOpen(false); onDelete(project.id); }}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                삭제
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Title */}
      <h3 className="font-semibold text-white mb-1 line-clamp-1">{project.name}</h3>
      <p className="text-slate-400 text-xs mb-4 line-clamp-2 leading-relaxed">
        {project.description || '설명 없음'}
      </p>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 mb-4">
        <div className="bg-white/3 rounded-lg p-2.5">
          <div className="text-xs text-slate-500 mb-0.5">필지 수</div>
          <div className="font-semibold text-white text-sm">{(project.plot_count || 0).toLocaleString()}</div>
        </div>
        <div className="bg-white/3 rounded-lg p-2.5">
          <div className="text-xs text-slate-500 mb-0.5">HIGH 위험</div>
          <div className={`font-semibold text-sm ${(project.high_risk_count || 0) > 0 ? 'text-red-400' : 'text-slate-400'}`}>
            {project.high_risk_count || 0}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-white/5">
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          {statusIcon}
          <StatusBadge status={project.status || 'created'} />
        </div>
        <Link
          to={`/projects/${project.id}`}
          className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300 font-medium transition-colors"
        >
          상세보기 <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* Date */}
      <div className="mt-2 flex items-center gap-1 text-xs text-slate-600">
        <Calendar className="w-3 h-3" />
        {project.created_at ? new Date(project.created_at).toLocaleDateString('ko-KR') : '—'}
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);

  const loadProjects = async () => {
    setLoading(true);
    try {
      const r = await projectsAPI.list();
      const projs = r.data || [];
      const enriched = await Promise.all(projs.map(async (p) => {
        try {
          const jobsR = await analysisAPI.projectJobs(p.id);
          const doneJobs = (jobsR.data || []).filter(j => j.status === 'done' || j.status === 'completed');
          if (doneJobs.length > 0) {
            const sumR = await analysisAPI.jobSummary(doneJobs[0].id);
            const s = sumR.data || {};
            return { ...p, status: 'done', high_risk_count: s.high || 0 };
          }
        } catch {}
        return p;
      }));
      setProjects(enriched);
    } catch {
      toast.error('프로젝트 목록을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadProjects(); }, []);

  const handleDelete = async (id) => {
    if (!confirm('이 프로젝트를 삭제하시겠습니까?')) return;
    try {
      await projectsAPI.delete(id);
      setProjects(ps => ps.filter(p => p.id !== id));
      toast.success('프로젝트가 삭제되었습니다.');
    } catch {
      toast.error('삭제에 실패했습니다.');
    }
  };

  const filtered = projects.filter(p =>
    p.name?.toLowerCase().includes(search.toLowerCase()) ||
    p.description?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">프로젝트</h1>
          <p className="text-slate-400 text-sm mt-1">공급망 분석 프로젝트를 관리하세요.</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary px-5 py-2.5 rounded-xl text-sm">
          <Plus className="w-4 h-4" /> 새 프로젝트
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          className="form-input pl-11"
          placeholder="프로젝트 검색..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 spinner" />
            <span className="text-slate-400 text-sm">불러오는 중...</span>
          </div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <FolderOpen className="w-16 h-16 text-slate-700 mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">
            {search ? '검색 결과가 없습니다' : '프로젝트가 없습니다'}
          </h3>
          <p className="text-slate-400 text-sm mb-6 max-w-sm">
            {search ? `"${search}"에 해당하는 프로젝트를 찾을 수 없습니다.` : '새 프로젝트를 만들어 공급망 분석을 시작하세요.'}
          </p>
          {!search && (
            <button onClick={() => setShowCreate(true)} className="btn-primary px-6 py-3 rounded-xl">
              <Plus className="w-4 h-4" /> 첫 번째 프로젝트 만들기
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map(p => (
            <ProjectCard key={p.id} project={p} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {showCreate && (
        <CreateProjectModal
          onClose={() => setShowCreate(false)}
          onCreated={(p) => setProjects(ps => [p, ...ps])}
        />
      )}
    </div>
  );
}

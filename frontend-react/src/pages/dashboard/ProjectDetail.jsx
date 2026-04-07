import { useState, useEffect, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Upload, Play, RefreshCw, MapPin, BarChart3,
  FileText, Clock, Trash2, AlertTriangle, CheckCircle,
  Loader, XCircle, Download, Plus, X, Eye
} from 'lucide-react';
import { projectsAPI, plotsAPI, analysisAPI } from '../../api/client';
import toast from 'react-hot-toast';

const TABS = ['개요', '필지', '분석', '결과', '증빙', '이력'];

function TabBar({ active, onChange }) {
  return (
    <div className="flex gap-0 border-b border-white/10 overflow-x-auto">
      {TABS.map(t => (
        <button key={t} className={`tab-btn ${active === t ? 'active' : ''}`} onClick={() => onChange(t)}>
          {t}
        </button>
      ))}
    </div>
  );
}

function OverviewTab({ project }) {
  return (
    <div className="grid md:grid-cols-2 gap-6">
      <div className="glass rounded-2xl p-6">
        <h3 className="font-semibold text-white mb-4">프로젝트 정보</h3>
        <div className="space-y-3">
          {[
            { label: '이름', value: project.name },
            { label: '설명', value: project.description || '—' },
            { label: '상태', value: project.status || 'created' },
            { label: '생성일', value: project.created_at ? new Date(project.created_at).toLocaleString('ko-KR') : '—' },
            { label: '마지막 분석', value: project.last_analyzed_at ? new Date(project.last_analyzed_at).toLocaleString('ko-KR') : '—' },
          ].map((item, i) => (
            <div key={i} className="flex justify-between text-sm border-b border-white/5 pb-2 last:border-0">
              <span className="text-slate-400">{item.label}</span>
              <span className="text-white font-medium text-right max-w-[200px]">{item.value}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="glass rounded-2xl p-6">
        <h3 className="font-semibold text-white mb-4">분석 현황</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-sm">총 필지</span>
            <span className="text-2xl font-bold text-white">{(project.plot_count || 0).toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-sm">HIGH 위험</span>
            <span className={`text-2xl font-bold ${(project.high_risk_count || 0) > 0 ? 'text-red-400' : 'text-slate-400'}`}>
              {project.high_risk_count || 0}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-sm">REVIEW 위험</span>
            <span className={`text-2xl font-bold ${(project.review_count || 0) > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
              {project.review_count || 0}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-sm">LOW (정상)</span>
            <span className="text-2xl font-bold text-emerald-400">{project.low_count || 0}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function PlotsTab({ projectId }) {
  const [plots, setPlots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    plotsAPI.list(projectId)
      .then(r => setPlots(r.data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    try {
      await plotsAPI.upload(projectId, file);
      toast.success('필지 데이터가 업로드되었습니다.');
      plotsAPI.list(projectId).then(r => setPlots(r.data || []));
    } catch (err) {
      toast.error(err.response?.data?.detail || '업로드에 실패했습니다.');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = async (plotId) => {
    if (!confirm('이 필지를 삭제하시겠습니까?')) return;
    try {
      await plotsAPI.delete(plotId);
      setPlots(ps => ps.filter(p => p.id !== plotId));
      toast.success('필지가 삭제되었습니다.');
    } catch {
      toast.error('삭제에 실패했습니다.');
    }
  };

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div className="text-sm text-slate-400">총 {plots.length.toLocaleString()}개 필지</div>
        <div className="flex gap-2">
          <input type="file" ref={fileRef} accept=".csv,.geojson,.json,.zip" className="hidden" onChange={handleUpload} />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="btn-primary text-sm px-4 py-2 rounded-xl disabled:opacity-50"
          >
            {uploading ? <><div className="w-3.5 h-3.5 spinner" />업로드 중...</> : <><Upload className="w-3.5 h-3.5" />CSV/GeoJSON 업로드</>}
          </button>
        </div>
      </div>

      <div className="glass rounded-2xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12"><div className="w-8 h-8 spinner" /></div>
        ) : plots.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center px-4">
            <MapPin className="w-12 h-12 text-slate-600 mb-3" />
            <div className="text-slate-400 font-medium mb-1">등록된 필지가 없습니다</div>
            <div className="text-slate-600 text-sm mb-4">CSV 또는 GeoJSON 파일을 업로드하여 필지를 추가하세요.</div>
            <button onClick={() => fileRef.current?.click()} className="btn-primary text-sm px-5 py-2 rounded-xl">
              <Upload className="w-4 h-4" /> 파일 업로드
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table w-full">
              <thead>
                <tr>
                  <th>#</th>
                  <th>위도</th>
                  <th>경도</th>
                  <th>면적 (ha)</th>
                  <th>위험 등급</th>
                  <th>상태</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {plots.slice(0, 100).map((p, i) => (
                  <tr key={p.id}>
                    <td className="text-slate-500 text-xs">{i + 1}</td>
                    <td>{p.latitude?.toFixed(6) || '—'}</td>
                    <td>{p.longitude?.toFixed(6) || '—'}</td>
                    <td>{p.area_ha?.toFixed(2) || '—'}</td>
                    <td>
                      {p.risk_level ? (
                        <span className={
                          p.risk_level === 'HIGH' ? 'badge-high' :
                          p.risk_level === 'REVIEW' ? 'badge-review' : 'badge-low'
                        }>{p.risk_level}</span>
                      ) : <span className="text-slate-600">미분석</span>}
                    </td>
                    <td>
                      <span className={`text-xs ${p.is_valid === false ? 'text-red-400' : 'text-emerald-400'}`}>
                        {p.is_valid === false ? '유효하지 않음' : '유효'}
                      </span>
                    </td>
                    <td>
                      <button onClick={() => handleDelete(p.id)} className="text-slate-600 hover:text-red-400 transition-colors p-1">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {plots.length > 100 && (
              <div className="text-center py-3 text-slate-500 text-sm">
                {plots.length - 100}개 더 있습니다
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function AnalysisTab({ projectId, project }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const loadJobs = () => {
    analysisAPI.projectJobs(projectId)
      .then(r => setJobs(r.data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadJobs(); }, [projectId]);

  const handleRun = async () => {
    if (project.plot_count === 0) {
      toast.error('먼저 필지 데이터를 업로드해주세요.');
      return;
    }
    setRunning(true);
    try {
      await analysisAPI.run(projectId);
      toast.success('분석이 시작되었습니다! 완료까지 수 분이 걸릴 수 있습니다.');
      setTimeout(loadJobs, 2000);
    } catch (err) {
      toast.error(err.response?.data?.detail || '분석 실행에 실패했습니다.');
    } finally {
      setRunning(false);
    }
  };

  const statusIcon = (s) => ({
    completed: <CheckCircle className="w-4 h-4 text-emerald-400" />,
    running: <Loader className="w-4 h-4 text-sky-400 animate-spin" />,
    failed: <XCircle className="w-4 h-4 text-red-400" />,
  }[s] || <Clock className="w-4 h-4 text-amber-400" />);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="text-sm text-slate-400">분석 작업 이력</div>
        <div className="flex gap-2">
          <button onClick={loadJobs} className="btn-secondary text-sm px-3 py-2 rounded-xl">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleRun}
            disabled={running}
            className="btn-primary text-sm px-5 py-2 rounded-xl disabled:opacity-50"
          >
            {running ? <><div className="w-3.5 h-3.5 spinner" />실행 중...</> : <><Play className="w-3.5 h-3.5" />분석 실행</>}
          </button>
        </div>
      </div>

      <div className="glass rounded-2xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12"><div className="w-8 h-8 spinner" /></div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center px-4">
            <BarChart3 className="w-12 h-12 text-slate-600 mb-3" />
            <div className="text-slate-400 font-medium mb-1">분석 이력이 없습니다</div>
            <div className="text-slate-600 text-sm mb-4">분석 실행 버튼을 클릭하여 위성 데이터 분석을 시작하세요.</div>
          </div>
        ) : (
          <table className="data-table w-full">
            <thead>
              <tr>
                <th>작업 ID</th>
                <th>상태</th>
                <th>필지 수</th>
                <th>HIGH</th>
                <th>시작 시각</th>
                <th>완료 시각</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map(j => (
                <tr key={j.id}>
                  <td className="font-mono text-xs text-slate-400">{j.id?.slice(0, 8)}...</td>
                  <td>
                    <span className="flex items-center gap-1.5">
                      {statusIcon(j.status)}
                      <span className={`text-xs font-medium ${
                        j.status === 'done' || j.status === 'completed' ? 'text-emerald-400' :
                        j.status === 'running' ? 'text-sky-400' :
                        j.status === 'failed' ? 'text-red-400' : 'text-amber-400'
                      }`}>{j.status}</span>
                    </span>
                  </td>
                  <td>{(j.total_plots || 0).toLocaleString()}</td>
                  <td className={`font-medium ${(j.high || 0) > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                    {j.high || 0}
                  </td>
                  <td className="text-slate-500 text-xs">{j.started_at ? new Date(j.started_at).toLocaleString('ko-KR') : '—'}</td>
                  <td className="text-slate-500 text-xs">{j.completed_at ? new Date(j.completed_at).toLocaleString('ko-KR') : '—'}</td>
                  <td>
                    {j.status === 'done' || j.status === 'completed' && (
                      <Link to={`/projects/${projectId}/results`} state={{ jobId: j.id }}
                        className="text-sky-400 hover:text-sky-300 text-xs flex items-center gap-1 transition-colors">
                        <Eye className="w-3.5 h-3.5" /> 결과
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default function ProjectDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('개요');

  useEffect(() => {
    projectsAPI.get(id)
      .then(r => setProject(r.data))
      .catch(() => { toast.error('프로젝트를 불러오지 못했습니다.'); navigate('/projects'); })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 spinner" />
        <span className="text-slate-400 text-sm">로딩 중...</span>
      </div>
    </div>
  );

  if (!project) return null;

  const renderTab = () => {
    switch (activeTab) {
      case '개요': return <OverviewTab project={project} />;
      case '필지': return <PlotsTab projectId={id} />;
      case '분석': return <AnalysisTab projectId={id} project={project} />;
      case '결과': return (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <BarChart3 className="w-12 h-12 text-slate-600 mb-3" />
          <div className="text-slate-400 font-medium mb-2">분석 결과 페이지로 이동하세요</div>
          <Link to={`/projects/${id}/results`} className="btn-primary text-sm px-5 py-2 rounded-xl">
            결과 보기 <ArrowLeft className="w-4 h-4 rotate-180" />
          </Link>
        </div>
      );
      case '증빙': return (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Download className="w-12 h-12 text-slate-600 mb-3" />
          <div className="text-slate-400 font-medium mb-2">보고서 다운로드 페이지로 이동하세요</div>
          <Link to={`/projects/${id}/export`} className="btn-primary text-sm px-5 py-2 rounded-xl">
            보고서 내보내기
          </Link>
        </div>
      );
      case '이력': return (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Clock className="w-12 h-12 text-slate-600 mb-3" />
          <div className="text-slate-400 font-medium mb-2">감사 이력 페이지로 이동하세요</div>
          <Link to={`/projects/${id}/history`} className="btn-primary text-sm px-5 py-2 rounded-xl">
            이력 보기
          </Link>
        </div>
      );
      default: return null;
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Breadcrumb + Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-4">
          <Link to="/projects" className="hover:text-slate-300 transition-colors flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" /> 프로젝트
          </Link>
          <span>/</span>
          <span className="text-slate-300">{project.name}</span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white">{project.name}</h1>
            {project.description && (
              <p className="text-slate-400 text-sm mt-1">{project.description}</p>
            )}
          </div>
          <div className="flex gap-2">
            <Link to={`/projects/${id}/results`} className="btn-secondary text-sm px-4 py-2 rounded-xl">
              <BarChart3 className="w-3.5 h-3.5" /> 결과
            </Link>
            <Link to={`/projects/${id}/export`} className="btn-secondary text-sm px-4 py-2 rounded-xl">
              <Download className="w-3.5 h-3.5" /> 내보내기
            </Link>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6">
        <TabBar active={activeTab} onChange={setActiveTab} />
      </div>

      {/* Tab Content */}
      {renderTab()}
    </div>
  );
}

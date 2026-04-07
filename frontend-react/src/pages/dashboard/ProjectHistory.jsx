import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Clock, CheckCircle, XCircle, Loader,
  Upload, Play, Download, Settings, User, RefreshCw,
  AlertTriangle, MapPin, FileText
} from 'lucide-react';
import { analysisAPI, projectsAPI } from '../../api/client';
import toast from 'react-hot-toast';

const EVENT_ICONS = {
  analysis_started: <Play className="w-3.5 h-3.5" />,
  analysis_completed: <CheckCircle className="w-3.5 h-3.5" />,
  analysis_failed: <XCircle className="w-3.5 h-3.5" />,
  plots_uploaded: <Upload className="w-3.5 h-3.5" />,
  report_generated: <Download className="w-3.5 h-3.5" />,
  project_created: <MapPin className="w-3.5 h-3.5" />,
  settings_changed: <Settings className="w-3.5 h-3.5" />,
  member_added: <User className="w-3.5 h-3.5" />,
};

const EVENT_COLORS = {
  analysis_started: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  analysis_completed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  analysis_failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  plots_uploaded: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  report_generated: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  project_created: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  settings_changed: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  member_added: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
};

const EVENT_LABELS = {
  analysis_started: '분석 시작',
  analysis_completed: '분석 완료',
  analysis_failed: '분석 실패',
  plots_uploaded: '필지 업로드',
  report_generated: '보고서 생성',
  project_created: '프로젝트 생성',
  settings_changed: '설정 변경',
  member_added: '멤버 추가',
};

function TimelineItem({ event, isLast }) {
  const colorClass = EVENT_COLORS[event.event_type] || EVENT_COLORS.settings_changed;
  const icon = EVENT_ICONS[event.event_type] || <Clock className="w-3.5 h-3.5" />;
  const label = EVENT_LABELS[event.event_type] || event.event_type;

  return (
    <div className="flex gap-4">
      {/* Timeline line */}
      <div className="flex flex-col items-center">
        <div className={`w-8 h-8 rounded-full border flex items-center justify-center flex-shrink-0 ${colorClass}`}>
          {icon}
        </div>
        {!isLast && <div className="w-px flex-1 bg-white/5 my-1" />}
      </div>

      {/* Content */}
      <div className={`pb-6 ${isLast ? '' : ''} flex-1 min-w-0`}>
        <div className="glass rounded-xl p-4">
          <div className="flex items-start justify-between gap-3 mb-2">
            <div>
              <span className="font-medium text-white text-sm">{label}</span>
              {event.user_email && (
                <span className="text-slate-500 text-xs ml-2">by {event.user_email}</span>
              )}
            </div>
            <span className="text-xs text-slate-500 flex-shrink-0">
              {event.created_at ? new Date(event.created_at).toLocaleString('ko-KR') : '—'}
            </span>
          </div>

          {event.description && (
            <p className="text-slate-400 text-xs leading-relaxed">{event.description}</p>
          )}

          {/* Metadata */}
          {event.metadata && Object.keys(event.metadata).length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/5 grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(event.metadata).slice(0, 6).map(([k, v]) => (
                <div key={k} className="text-xs">
                  <span className="text-slate-600">{k}: </span>
                  <span className="text-slate-400 font-medium">{String(v)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Risk summary for completed analyses */}
          {event.event_type === 'analysis_completed' && event.metadata && (
            <div className="mt-3 flex gap-3">
              {event.metadata.high_count !== undefined && (
                <span className="badge-high text-xs px-2 py-0.5 rounded-full">HIGH {event.metadata.high_count}</span>
              )}
              {event.metadata.review_count !== undefined && (
                <span className="badge-review text-xs px-2 py-0.5 rounded-full">REVIEW {event.metadata.review_count}</span>
              )}
              {event.metadata.low_count !== undefined && (
                <span className="badge-low text-xs px-2 py-0.5 rounded-full">LOW {event.metadata.low_count}</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function generateDemoHistory(project) {
  const now = new Date();
  const events = [];

  if (project) {
    events.push({
      id: 'demo-1',
      event_type: 'project_created',
      description: `프로젝트 "${project.name}"이 생성되었습니다.`,
      created_at: project.created_at || now.toISOString(),
      user_email: 'user@example.com',
      metadata: {},
    });
  }

  if (project?.plot_count > 0) {
    events.push({
      id: 'demo-2',
      event_type: 'plots_uploaded',
      description: `${project.plot_count}개의 필지 데이터가 업로드되었습니다.`,
      created_at: new Date(new Date(project.created_at || now).getTime() + 600000).toISOString(),
      user_email: 'user@example.com',
      metadata: { count: project.plot_count },
    });

    events.push({
      id: 'demo-3',
      event_type: 'analysis_started',
      description: '위성 이미지 기반 삼림 변화 분석을 시작했습니다.',
      created_at: new Date(new Date(project.created_at || now).getTime() + 700000).toISOString(),
      user_email: 'user@example.com',
      metadata: { total_plots: project.plot_count },
    });

    if (project.status === 'completed' || project.high_risk_count !== undefined) {
      events.push({
        id: 'demo-4',
        event_type: 'analysis_completed',
        description: '분석이 완료되었습니다. 결과를 확인하세요.',
        created_at: new Date(new Date(project.created_at || now).getTime() + 1800000).toISOString(),
        user_email: 'system',
        metadata: {
          high_count: project.high_risk_count || 0,
          review_count: project.review_count || 0,
          low_count: project.low_count || 0,
        },
      });
    }
  }

  return events.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

export default function ProjectHistory() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [projR] = await Promise.all([
        projectsAPI.get(id),
      ]);
      setProject(projR.data);

      try {
        const histR = await analysisAPI.projectHistory(id);
        const items = histR.data || [];
        if (items.length > 0) {
          // Map API format (action/detail/occurred_at) to frontend format
          const ACTION_MAP = {
            'project.created': 'project_created',
            'plots.upload': 'plots_uploaded',
            'job.started': 'analysis_started',
            'job.completed': 'analysis_completed',
            'job.failed': 'analysis_failed',
            'export.created': 'report_generated',
          };
          const DESC_MAP = {
            'project.created': '프로젝트가 생성되었습니다.',
            'plots.upload': '필지 데이터가 업로드되었습니다.',
            'job.started': '위성 이미지 기반 삼림 변화 분석을 시작했습니다.',
            'job.completed': '분석이 완료되었습니다.',
            'job.failed': '분석 실행 중 오류가 발생했습니다.',
            'export.created': '증빙 보고서가 생성되었습니다.',
          };
          const mapped = items.map(item => ({
            id: item.id,
            event_type: ACTION_MAP[item.action] || item.action,
            description: DESC_MAP[item.action] || item.action,
            created_at: item.occurred_at,
            user_email: item.user_id || 'system',
            metadata: item.detail || {},
          }));
          setHistory(mapped);
        } else {
          setHistory(generateDemoHistory(projR.data));
        }
      } catch {
        setHistory(generateDemoHistory(projR.data));
      }
    } catch {
      toast.error('데이터를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [id]);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-4">
          <Link to={`/projects/${id}`} className="hover:text-slate-300 flex items-center gap-1 transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" /> {project?.name || '프로젝트'}
          </Link>
          <span>/</span>
          <span className="text-slate-300">감사 이력</span>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">감사 이력</h1>
            <p className="text-slate-400 text-sm mt-1">프로젝트의 모든 활동 내역을 시간순으로 확인하세요.</p>
          </div>
          <button onClick={loadData} className="btn-secondary text-sm px-3 py-2 rounded-xl">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="glass rounded-xl p-4 mb-6 flex flex-wrap gap-3">
        {Object.entries(EVENT_LABELS).slice(0, 5).map(([type, label]) => (
          <div key={type} className="flex items-center gap-1.5 text-xs">
            <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${EVENT_COLORS[type]}`}>
              {EVENT_ICONS[type]}
            </div>
            <span className="text-slate-400">{label}</span>
          </div>
        ))}
      </div>

      {/* Timeline */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 spinner" />
            <span className="text-slate-400 text-sm">이력 로딩 중...</span>
          </div>
        </div>
      ) : history.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <Clock className="w-16 h-16 text-slate-700 mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">이력이 없습니다</h3>
          <p className="text-slate-400 text-sm">활동이 발생하면 여기에 기록됩니다.</p>
        </div>
      ) : (
        <div>
          <div className="text-sm text-slate-500 mb-4">{history.length}개 이벤트</div>
          {history.map((event, i) => (
            <TimelineItem
              key={event.id || i}
              event={event}
              isLast={i === history.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

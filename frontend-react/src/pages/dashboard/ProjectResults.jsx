import { useState, useEffect } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import {
  ArrowLeft, AlertTriangle, CheckCircle, Filter, RefreshCw,
  Download, MapPin, Search, BarChart3
} from 'lucide-react';
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { analysisAPI, reportsAPI, projectsAPI } from '../../api/client';
import toast from 'react-hot-toast';

const RISK_COLORS = {
  HIGH: '#ef4444',
  REVIEW: '#f59e0b',
  LOW: '#10b981',
};

function RiskBadge({ level }) {
  const cls = level === 'HIGH' ? 'badge-high' : level === 'REVIEW' ? 'badge-review' : 'badge-low';
  return <span className={cls}>{level}</span>;
}

function SummaryBanner({ summary }) {
  if (!summary || summary.high === 0) return null;
  return (
    <div className="flex items-start gap-4 p-5 rounded-2xl mb-6 border border-red-500/30"
      style={{ background: 'rgba(239,68,68,0.08)' }}>
      <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center flex-shrink-0">
        <AlertTriangle className="w-5 h-5 text-red-400" />
      </div>
      <div>
        <div className="font-semibold text-red-400 mb-1">
          {summary.high}개 필지에서 HIGH 위험이 감지되었습니다
        </div>
        <div className="text-slate-400 text-sm">
          즉각적인 검토가 필요합니다. 해당 필지의 공급망을 일시 중단하고 <strong className="text-red-300">현장 실사(ground-truthing)</strong>를 실시하세요.
        </div>
        <div className="text-slate-500 text-xs mt-2 flex items-center gap-1">
          ⚠️ 위성 분석은 사전 스크리닝 도구입니다. 구름·계절 변화 등으로 인한 오탐 가능성이 있으므로, HIGH 등급 필지는 반드시 현장 확인을 병행하세요.
        </div>
      </div>
    </div>
  );
}

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    return (
      <div className="glass rounded-xl px-4 py-3 text-sm">
        <p className="font-semibold text-white">{payload[0].name}</p>
        <p className="text-slate-300">{payload[0].value}개 ({payload[0].payload.percent}%)</p>
      </div>
    );
  }
  return null;
};

export default function ProjectResults() {
  const { id } = useParams();
  const location = useLocation();
  const [project, setProject] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(location.state?.jobId || null);
  const [results, setResults] = useState([]);
  const [summary, setSummary] = useState(null);
  const [filter, setFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [resultsLoading, setResultsLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      projectsAPI.get(id).then(r => setProject(r.data)),
      analysisAPI.projectJobs(id).then(r => {
        const j = r.data || [];
        setJobs(j);
        const completed = j.filter(x => x.status === 'done' || x.status === 'completed');
        if (!selectedJob && completed.length > 0) {
          setSelectedJob(completed[0].id);
        }
      }),
    ]).catch(() => {}).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!selectedJob) return;
    setResultsLoading(true);
    Promise.all([
      analysisAPI.jobResults(selectedJob),
      analysisAPI.jobSummary(selectedJob),
    ]).then(([resR, sumR]) => {
      setResults(resR.data || []);
      setSummary(sumR.data);
    }).catch(() => {
      toast.error('결과를 불러오지 못했습니다.');
    }).finally(() => setResultsLoading(false));
  }, [selectedJob]);

  const pieData = summary ? [
    { name: 'HIGH', value: summary.high || 0, percent: Math.round((summary.high / (summary.total || 1)) * 100) },
    { name: 'REVIEW', value: summary.review || 0, percent: Math.round((summary.review / (summary.total || 1)) * 100) },
    { name: 'LOW', value: summary.low || 0, percent: Math.round((summary.low / (summary.total || 1)) * 100) },
  ].filter(d => d.value > 0) : [];

  const filteredResults = results.filter(r => {
    const matchFilter = filter === 'ALL' || r.risk_level === filter;
    const matchSearch = !search ||
      r.plot_ref?.toString().toLowerCase().includes(search) ||
      r.supplier_name?.toString().toLowerCase().includes(search) ||
      r.deforestation_area?.toString().includes(search);
    return matchFilter && matchSearch;
  });

  const completedJobs = jobs.filter(j => j.status === 'done' || j.status === 'completed');

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-4">
          <Link to={`/projects/${id}`} className="hover:text-slate-300 flex items-center gap-1 transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" /> {project?.name || '프로젝트'}
          </Link>
          <span>/</span>
          <span className="text-slate-300">분석 결과</span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-white">분석 결과</h1>
          <div className="flex items-center gap-2">
            {completedJobs.length > 1 && (
              <select
                className="form-input text-sm py-2 pr-8 w-auto"
                value={selectedJob || ''}
                onChange={e => setSelectedJob(e.target.value)}
              >
                {completedJobs.map(j => (
                  <option key={j.id} value={j.id}>
                    {new Date(j.completed_at).toLocaleDateString('ko-KR')} 분석
                  </option>
                ))}
              </select>
            )}
            <Link to={`/projects/${id}/export`} className="btn-primary text-sm px-4 py-2 rounded-xl">
              <Download className="w-3.5 h-3.5" /> 내보내기
            </Link>
          </div>
        </div>
      </div>

      {loading || resultsLoading ? (
        <div className="flex items-center justify-center py-24">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 spinner" />
            <span className="text-slate-400 text-sm">결과 로딩 중...</span>
          </div>
        </div>
      ) : !selectedJob ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <BarChart3 className="w-16 h-16 text-slate-700 mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">분석 결과가 없습니다</h3>
          <p className="text-slate-400 text-sm mb-6">프로젝트 분석을 먼저 실행하세요.</p>
          <Link to={`/projects/${id}`} className="btn-primary px-6 py-2.5 rounded-xl text-sm">
            분석 실행하기
          </Link>
        </div>
      ) : (
        <>
          <SummaryBanner summary={summary} />

          {/* Charts + Summary Cards */}
          <div className="grid md:grid-cols-3 gap-6 mb-8">
            {/* Donut Chart */}
            <div className="glass rounded-2xl p-6">
              <h3 className="font-semibold text-white mb-4">위험 등급 분포</h3>
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={RISK_COLORS[entry.name]} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-48 text-slate-500 text-sm">데이터 없음</div>
              )}
              <div className="flex justify-center gap-4 mt-2">
                {pieData.map(d => (
                  <div key={d.name} className="flex items-center gap-1.5 text-xs">
                    <div className="w-2 h-2 rounded-full" style={{ background: RISK_COLORS[d.name] }} />
                    <span className="text-slate-400">{d.name} {d.percent}%</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Summary Stats */}
            <div className="md:col-span-2 grid grid-cols-2 sm:grid-cols-4 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: '전체 필지', value: summary?.total || 0, color: 'text-white', bg: 'bg-white/5' },
                { label: 'HIGH', value: summary?.high || 0, color: 'text-red-400', bg: 'bg-red-500/10' },
                { label: 'REVIEW', value: summary?.review || 0, color: 'text-amber-400', bg: 'bg-amber-500/10' },
                { label: 'LOW', value: summary?.low || 0, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
              ].map((s, i) => (
                <div key={i} className={`${s.bg} rounded-xl p-4 text-center`}>
                  <div className={`text-2xl font-bold ${s.color} mb-1`}>{s.value.toLocaleString()}</div>
                  <div className="text-slate-500 text-xs">{s.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Filter + Search */}
          <div className="flex flex-col sm:flex-row gap-3 mb-4">
            <div className="flex gap-2">
              {['ALL', 'HIGH', 'REVIEW', 'LOW'].map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${filter === f
                    ? f === 'HIGH' ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                    : f === 'REVIEW' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                    : f === 'LOW' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'bg-white/10 text-white border border-white/20'
                    : 'text-slate-400 hover:text-white border border-transparent hover:border-white/10'
                  }`}
                >
                  {f === 'ALL' ? '전체' : f}
                </button>
              ))}
            </div>
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                className="form-input pl-10 py-2 text-sm"
                placeholder="필지 ID 검색..."
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>

          {/* Results Table */}
          <div className="glass rounded-2xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="data-table w-full">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>필지 Ref</th>
                    <th>공급업체</th>
                    <th>dNDVI</th>
                    <th>변화면적 (ha)</th>
                    <th>위험 등급</th>
                    <th>신뢰도</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredResults.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="text-center py-12 text-slate-500">
                        <MapPin className="w-8 h-8 mx-auto mb-2 opacity-40" />
                        해당 조건의 결과가 없습니다.
                      </td>
                    </tr>
                  ) : filteredResults.slice(0, 200).map((r, i) => (
                    <tr key={r.id || i}>
                      <td className="text-slate-600 text-xs">{i + 1}</td>
                      <td className="font-mono text-xs text-slate-300">{r.plot_ref || r.plot_id?.slice(0, 8) || '—'}</td>
                      <td className="text-slate-300">{r.supplier_name || '—'}</td>
                      <td className={`font-mono ${(r.delta_ndvi || 0) < -0.15 ? 'text-red-400 font-medium' : 'text-slate-400'}`}>
                        {r.delta_ndvi != null ? r.delta_ndvi.toFixed(3) : '—'}
                      </td>
                      <td className={`font-mono ${(r.changed_area_ha || 0) > 1 ? 'text-red-400 font-medium' : 'text-slate-400'}`}>
                        {r.changed_area_ha != null ? r.changed_area_ha.toFixed(2) : '0.00'}
                      </td>
                      <td><RiskBadge level={r.risk_level || 'LOW'} /></td>
                      <td>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-white/10 rounded-full h-1.5 max-w-16">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${(r.confidence || 0) * 100}%`,
                                background: RISK_COLORS[r.risk_level] || '#10b981',
                              }}
                            />
                          </div>
                          <span className="text-xs text-slate-400">
                            {((r.confidence || 0) * 100).toFixed(0)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {filteredResults.length > 200 && (
              <div className="text-center py-4 text-slate-500 text-sm border-t border-white/5">
                {filteredResults.length - 200}개 더 있습니다
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

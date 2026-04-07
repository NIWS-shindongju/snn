import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Download, FileText, FileJson, Table,
  Loader, CheckCircle, Clock, RefreshCw, ExternalLink
} from 'lucide-react';
import { analysisAPI, reportsAPI, projectsAPI } from '../../api/client';
import toast from 'react-hot-toast';

const FORMAT_INFO = {
  pdf: {
    icon: <FileText className="w-8 h-8" />,
    title: 'PDF 보고서',
    desc: '경영진 보고용 전문 PDF 보고서. EUDR 규정 준수 현황, 위험 분석 요약, 필지 목록을 포함합니다.',
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/20',
    ext: '.pdf',
    badge: 'EUDR 증빙',
  },
  json: {
    icon: <FileJson className="w-8 h-8" />,
    title: 'JSON 데이터',
    desc: '시스템 연동을 위한 구조화된 JSON 포맷. 모든 필지 분석 결과와 메타데이터를 포함합니다.',
    color: 'text-sky-400',
    bg: 'bg-sky-500/10',
    border: 'border-sky-500/20',
    ext: '.json',
    badge: 'API 연동',
  },
  csv: {
    icon: <Table className="w-8 h-8" />,
    title: 'CSV 스프레드시트',
    desc: 'Excel, Google Sheets 호환 CSV 파일. 필지 좌표, 면적, 위험 등급, 삼림 손실 면적을 포함합니다.',
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/20',
    ext: '.csv',
    badge: '엑셀 호환',
  },
};

function ReportCard({ format, jobId, existingReports, onGenerate }) {
  const info = FORMAT_INFO[format];
  const existing = existingReports.find(r => r.format === format);
  const [generating, setGenerating] = useState(false);

  const handleGenerate = async () => {
    if (!jobId) { toast.error('먼저 분석을 완료해주세요.'); return; }
    setGenerating(true);
    try {
      const r = await reportsAPI.generate(jobId, format);
      toast.success(`${info.title} 생성이 시작되었습니다.`);
      onGenerate(r.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || '보고서 생성에 실패했습니다.');
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async () => {
    if (!existing?.id) return;
    try {
      await reportsAPI.download(existing.id, `TraceCheck_${format}${info.ext}`);
    } catch (err) {
      toast.error('다운로드에 실패했습니다.');
    }
  };

  return (
    <div className={`glass rounded-2xl p-6 border ${info.border} card-hover`}>
      <div className="flex items-start justify-between mb-5">
        <div className={`w-14 h-14 rounded-2xl ${info.bg} ${info.color} flex items-center justify-center`}>
          {info.icon}
        </div>
        <span className={`text-xs font-semibold px-3 py-1 rounded-full ${info.bg} ${info.color} border ${info.border}`}>
          {info.badge}
        </span>
      </div>

      <h3 className="text-lg font-semibold text-white mb-2">{info.title}</h3>
      <p className="text-slate-400 text-sm leading-relaxed mb-6">{info.desc}</p>

      {/* Existing report info */}
      {existing && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-white/3 border border-white/5 mb-4">
          <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <div className="min-w-0">
            <div className="text-xs text-slate-300 font-medium">생성 완료</div>
            <div className="text-xs text-slate-600 truncate">
              {existing.generated_at ? new Date(existing.generated_at).toLocaleString('ko-KR') : ''}
            </div>
          </div>
          {existing.file_size_bytes && (
            <span className="text-xs text-slate-500 ml-auto">
              {(existing.file_size_bytes / 1024).toFixed(0)}KB
            </span>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2">
        {existing ? (
          <>
            <button
              onClick={handleDownload}
              className="btn-primary flex-1 justify-center py-2.5 rounded-xl text-sm"
            >
              <Download className="w-4 h-4" /> 다운로드{info.ext}
            </button>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="btn-secondary px-3 py-2.5 rounded-xl text-sm"
              title="재생성"
            >
              <RefreshCw className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
            </button>
          </>
        ) : (
          <button
            onClick={handleGenerate}
            disabled={generating || !jobId}
            className="btn-primary w-full justify-center py-2.5 rounded-xl text-sm disabled:opacity-50"
          >
            {generating ? (
              <><div className="w-4 h-4 spinner" /> 생성 중...</>
            ) : (
              <><Download className="w-4 h-4" /> {info.title} 생성</>
            )}
          </button>
        )}
      </div>
    </div>
  );
}

export default function ProjectExport() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [latestJob, setLatestJob] = useState(null);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [projR, jobsR] = await Promise.all([
        projectsAPI.get(id),
        analysisAPI.projectJobs(id),
      ]);
      setProject(projR.data);
      const completedJobs = (jobsR.data || []).filter(j => j.status === 'done' || j.status === 'completed');
      if (completedJobs.length > 0) {
        const job = completedJobs[0];
        // Fetch summary to get risk counts
        try {
          const sumR = await analysisAPI.jobSummary(job.id);
          const sum = sumR.data || {};
          job.high = sum.high || 0;
          job.review = sum.review || 0;
          job.low = sum.low || 0;
        } catch {}
        setLatestJob(job);
        const repsR = await reportsAPI.list(job.id);
        setReports(repsR.data || []);
      }
    } catch (err) {
      toast.error('데이터를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [id]);

  const handleGenerated = (report) => {
    setReports(rs => {
      const idx = rs.findIndex(r => r.format === report.format);
      if (idx >= 0) {
        const copy = [...rs];
        copy[idx] = report;
        return copy;
      }
      return [report, ...rs];
    });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-4">
          <Link to={`/projects/${id}`} className="hover:text-slate-300 flex items-center gap-1 transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" /> {project?.name || '프로젝트'}
          </Link>
          <span>/</span>
          <span className="text-slate-300">보고서 내보내기</span>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">보고서 내보내기</h1>
            <p className="text-slate-400 text-sm mt-1">EUDR 규정 준수 증빙 문서를 다양한 형식으로 다운로드하세요.</p>
          </div>
          <button onClick={loadData} className="btn-secondary text-sm px-3 py-2 rounded-xl">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Alert: no completed job */}
      {!loading && !latestJob && (
        <div className="glass rounded-2xl p-5 border border-amber-500/20 mb-6 flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center flex-shrink-0">
            <Clock className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <div className="font-semibold text-amber-400 mb-1">분석 완료 후 보고서를 생성할 수 있습니다</div>
            <div className="text-slate-400 text-sm">
              프로젝트 분석을 먼저 실행해주세요.{' '}
              <Link to={`/projects/${id}`} className="text-sky-400 hover:text-sky-300 transition-colors">
                분석 탭으로 이동 →
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Selected job info */}
      {latestJob && (
        <div className="glass rounded-xl p-4 mb-6 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            <div>
              <span className="text-sm text-white font-medium">최신 완료 분석</span>
              <span className="text-slate-500 text-xs ml-2">
                {latestJob.completed_at ? new Date(latestJob.completed_at).toLocaleString('ko-KR') : ''}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-400">
            <span>총 {(latestJob.total_plots || 0).toLocaleString()}개 필지</span>
            <span className="text-red-400 font-medium">HIGH {latestJob.high || 0}</span>
            <span className="text-amber-400">REVIEW {latestJob.review || 0}</span>
            <span className="text-emerald-400">LOW {latestJob.low || 0}</span>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="w-10 h-10 spinner" />
        </div>
      ) : (
        <div className="grid md:grid-cols-3 gap-6">
          {['pdf', 'json', 'csv'].map(fmt => (
            <ReportCard
              key={fmt}
              format={fmt}
              jobId={latestJob?.id}
              existingReports={reports}
              onGenerate={handleGenerated}
            />
          ))}
        </div>
      )}

      {/* Info note */}
      <div className="mt-8 glass rounded-2xl p-5">
        <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
          <FileText className="w-4 h-4 text-emerald-400" />
          보고서 활용 안내
        </h3>
        <div className="grid sm:grid-cols-3 gap-4">
          {[
            { title: 'EUDR DDS 제출', desc: 'PDF 보고서를 EU 당국 제출용 Due Diligence Statement 첨부 자료로 활용하세요.' },
            { title: '내부 감사', desc: 'CSV 파일을 사내 ESG 관리 시스템에 업로드하여 공급망 위험을 추적하세요.' },
            { title: '시스템 연동', desc: 'JSON API 응답으로 ERP/SCM 시스템과 자동 연동하세요.' },
          ].map((item, i) => (
            <div key={i} className="border-l-2 border-emerald-500/30 pl-3">
              <div className="text-sm font-medium text-white mb-1">{item.title}</div>
              <div className="text-xs text-slate-400 leading-relaxed">{item.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

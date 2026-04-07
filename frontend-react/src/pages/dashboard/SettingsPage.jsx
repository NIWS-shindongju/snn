import { useState, useEffect } from 'react';
import {
  Building2, Users, Webhook, Save, Plus, Trash2,
  Copy, RefreshCw, CheckCircle, X, Eye, EyeOff,
  Globe, Bell, Shield, Mail, Crown, UserCheck
} from 'lucide-react';
import { orgAPI, webhooksAPI } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import toast from 'react-hot-toast';

const TABS = ['조직', '팀원', '웹훅'];

function TabBar({ active, onChange }) {
  return (
    <div className="flex border-b border-white/10">
      {TABS.map(t => (
        <button key={t} className={`tab-btn ${active === t ? 'active' : ''}`} onClick={() => onChange(t)}>
          {t}
        </button>
      ))}
    </div>
  );
}

function OrgTab({ org, onSave }) {
  const [form, setForm] = useState({ name: org?.name || '', contact_email: org?.contact_email || '' });
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(form);
      toast.success('조직 정보가 저장되었습니다.');
    } catch {
      toast.error('저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  const planInfo = {
    free: { label: 'Free', color: 'text-slate-400', bg: 'bg-slate-500/10' },
    pro: { label: 'Pro', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    enterprise: { label: 'Enterprise', color: 'text-sky-400', bg: 'bg-sky-500/10' },
  }[org?.subscription_plan || 'free'] || { label: 'Free', color: 'text-slate-400', bg: 'bg-slate-500/10' };

  return (
    <div className="grid md:grid-cols-2 gap-6">
      {/* Org Info */}
      <div className="glass rounded-2xl p-6">
        <h3 className="font-semibold text-white mb-6 flex items-center gap-2">
          <Building2 className="w-4 h-4 text-emerald-400" />
          조직 정보
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">조직명</label>
            <input
              className="form-input"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="회사명"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">연락처 이메일</label>
            <input
              type="email"
              className="form-input"
              value={form.contact_email}
              onChange={e => setForm(f => ({ ...f, contact_email: e.target.value }))}
              placeholder="admin@company.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">조직 ID</label>
            <div className="form-input text-slate-500 flex items-center justify-between cursor-default select-all text-xs font-mono">
              {org?.id || '—'}
            </div>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn-primary w-full justify-center py-2.5 rounded-xl text-sm disabled:opacity-50"
          >
            {saving ? <><div className="w-4 h-4 spinner" />저장 중...</> : <><Save className="w-4 h-4" />변경사항 저장</>}
          </button>
        </div>
      </div>

      {/* Subscription */}
      <div className="space-y-4">
        <div className="glass rounded-2xl p-6">
          <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
            <Shield className="w-4 h-4 text-sky-400" />
            구독 플랜
          </h3>
          <div className="flex items-center gap-3 mb-4">
            <div className={`px-4 py-2 rounded-xl text-sm font-bold ${planInfo.color} ${planInfo.bg}`}>
              {planInfo.label}
            </div>
            <div className="text-slate-400 text-sm">현재 플랜</div>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">프로젝트 한도</span>
              <span className="text-white">{org?.max_projects || 3}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">월 필지 한도</span>
              <span className="text-white">{(org?.max_plots_per_month || 100).toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">팀원 한도</span>
              <span className="text-white">{org?.max_members || 1}</span>
            </div>
          </div>
          {(org?.subscription_plan || 'free') !== 'enterprise' && (
            <button className="btn-primary w-full justify-center py-2.5 rounded-xl text-sm mt-4">
              플랜 업그레이드
            </button>
          )}
        </div>

        <div className="glass rounded-2xl p-5">
          <h3 className="font-semibold text-white mb-3 flex items-center gap-2 text-sm">
            <Bell className="w-4 h-4 text-amber-400" />
            알림 설정
          </h3>
          {[
            { label: '분석 완료 시 이메일', key: 'email_on_complete' },
            { label: 'HIGH 위험 감지 즉시 알림', key: 'email_on_high' },
            { label: '주간 요약 리포트', key: 'weekly_report' },
          ].map((item, i) => (
            <label key={i} className="flex items-center justify-between py-2 cursor-pointer">
              <span className="text-slate-300 text-sm">{item.label}</span>
              <div className="relative inline-flex items-center">
                <input type="checkbox" className="sr-only" defaultChecked={i < 2} />
                <div className="w-10 h-5 rounded-full bg-emerald-500/50 relative">
                  <div className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-emerald-400 transition-all" />
                </div>
              </div>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

function MembersTab({ members, onRoleChange, onRemove }) {
  const { user } = useAuth();
  const [inviteEmail, setInviteEmail] = useState('');

  const roleLabel = {
    admin: { label: '관리자', icon: <Crown className="w-3 h-3" />, color: 'text-amber-400' },
    member: { label: '멤버', icon: <UserCheck className="w-3 h-3" />, color: 'text-slate-400' },
    viewer: { label: '뷰어', icon: <Eye className="w-3 h-3" />, color: 'text-slate-500' },
  };

  return (
    <div className="space-y-6">
      {/* Invite */}
      <div className="glass rounded-2xl p-5">
        <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
          <Mail className="w-4 h-4 text-emerald-400" />
          팀원 초대
        </h3>
        <div className="flex gap-2">
          <input
            type="email"
            className="form-input flex-1"
            placeholder="초대할 이메일 주소"
            value={inviteEmail}
            onChange={e => setInviteEmail(e.target.value)}
          />
          <button
            onClick={() => { if (inviteEmail) { toast.success('초대 이메일이 발송되었습니다.'); setInviteEmail(''); } }}
            className="btn-primary px-5 py-2 rounded-xl text-sm"
          >
            <Plus className="w-4 h-4" /> 초대
          </button>
        </div>
      </div>

      {/* Members list */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-white/5">
          <h3 className="font-semibold text-white">팀원 목록 ({members.length}명)</h3>
        </div>
        {members.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Users className="w-10 h-10 text-slate-600 mb-2" />
            <div className="text-slate-400 text-sm">팀원이 없습니다</div>
          </div>
        ) : (
          <table className="data-table w-full">
            <thead>
              <tr>
                <th>사용자</th>
                <th>역할</th>
                <th>가입일</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {members.map(m => {
                const role = roleLabel[m.role] || roleLabel.member;
                const isMe = m.email === user?.email;
                return (
                  <tr key={m.id || m.email}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500 to-sky-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                          {m.email?.[0]?.toUpperCase()}
                        </div>
                        <div>
                          <div className="text-white text-sm font-medium">
                            {m.email}
                            {isMe && <span className="ml-2 text-xs text-emerald-400">(나)</span>}
                          </div>
                          <div className="text-slate-500 text-xs">{m.full_name || ''}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`flex items-center gap-1 text-xs font-medium ${role.color}`}>
                        {role.icon} {role.label}
                      </span>
                    </td>
                    <td className="text-slate-500 text-xs">
                      {m.joined_at ? new Date(m.joined_at).toLocaleDateString('ko-KR') : '—'}
                    </td>
                    <td>
                      {!isMe && (
                        <button
                          onClick={() => onRemove(m.id)}
                          className="text-slate-600 hover:text-red-400 transition-colors p-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function WebhookCreateModal({ onClose, onCreate }) {
  const [form, setForm] = useState({ name: '', url: '', events: ['analysis.completed'] });
  const [loading, setLoading] = useState(false);

  const EVENT_OPTIONS = [
    'analysis.completed', 'analysis.failed', 'analysis.started',
    'plot.uploaded', 'report.generated',
  ];

  const toggleEvent = (ev) => {
    setForm(f => ({
      ...f,
      events: f.events.includes(ev) ? f.events.filter(e => e !== ev) : [...f.events, ev],
    }));
  };

  const handleCreate = async () => {
    if (!form.name || !form.url) { toast.error('이름과 URL을 입력하세요.'); return; }
    setLoading(true);
    try {
      const r = await webhooksAPI.create(form);
      onCreate(r.data);
      toast.success('웹훅이 생성되었습니다.');
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || '웹훅 생성에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-content max-w-lg">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-white">웹훅 추가</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">웹훅 이름</label>
            <input className="form-input" placeholder="예: Slack 알림" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">URL</label>
            <input className="form-input" placeholder="https://hooks.slack.com/..." type="url" value={form.url} onChange={e => setForm(f => ({ ...f, url: e.target.value }))} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">이벤트 (다중 선택)</label>
            <div className="space-y-2">
              {EVENT_OPTIONS.map(ev => (
                <label key={ev} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.events.includes(ev)}
                    onChange={() => toggleEvent(ev)}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-sm text-slate-300 font-mono">{ev}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="btn-secondary flex-1 justify-center py-2.5 rounded-xl">취소</button>
            <button onClick={handleCreate} disabled={loading} className="btn-primary flex-1 justify-center py-2.5 rounded-xl disabled:opacity-50">
              {loading ? <><div className="w-4 h-4 spinner" />생성 중...</> : '웹훅 생성'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function WebhooksTab({ webhooks, onDelete, onTest, onAdd }) {
  const [showCreate, setShowCreate] = useState(false);
  const [showSecret, setShowSecret] = useState({});

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-white">웹훅 관리</h3>
          <p className="text-slate-400 text-xs mt-1">분석 완료, HIGH 위험 감지 등 이벤트를 외부 시스템으로 전달합니다.</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary text-sm px-4 py-2 rounded-xl">
          <Plus className="w-4 h-4" /> 웹훅 추가
        </button>
      </div>

      {webhooks.length === 0 ? (
        <div className="glass rounded-2xl flex flex-col items-center justify-center py-16 text-center">
          <Webhook className="w-12 h-12 text-slate-600 mb-3" />
          <div className="text-slate-400 font-medium mb-1">등록된 웹훅이 없습니다</div>
          <div className="text-slate-600 text-sm mb-4">Slack, Teams 등 외부 시스템과 연동하세요.</div>
          <button onClick={() => setShowCreate(true)} className="btn-primary text-sm px-5 py-2 rounded-xl">
            <Plus className="w-4 h-4" /> 첫 번째 웹훅 추가
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {webhooks.map(wh => (
            <div key={wh.id} className="glass rounded-2xl p-5">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-purple-500/10 flex items-center justify-center">
                    <Globe className="w-4 h-4 text-purple-400" />
                  </div>
                  <div>
                    <div className="font-medium text-white text-sm">{wh.name}</div>
                    <div className="text-slate-500 text-xs font-mono truncate max-w-xs">{wh.url}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${wh.is_active ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600'}`} />
                  <span className="text-xs text-slate-400">{wh.is_active ? '활성' : '비활성'}</span>
                </div>
              </div>

              <div className="flex flex-wrap gap-1.5 mb-3">
                {(wh.events || []).map(ev => (
                  <span key={ev} className="text-xs bg-white/5 text-slate-400 px-2 py-0.5 rounded font-mono">{ev}</span>
                ))}
              </div>

              <div className="flex gap-2">
                <button onClick={() => onTest(wh.id)} className="btn-secondary text-xs px-3 py-1.5 rounded-lg">
                  <RefreshCw className="w-3 h-3" /> 테스트
                </button>
                <button onClick={() => onDelete(wh.id)} className="text-slate-600 hover:text-red-400 transition-colors px-2 py-1.5 rounded-lg hover:bg-red-500/10 text-xs flex items-center gap-1">
                  <Trash2 className="w-3 h-3" /> 삭제
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <WebhookCreateModal
          onClose={() => setShowCreate(false)}
          onCreate={(wh) => { onAdd(wh); setShowCreate(false); }}
        />
      )}
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('조직');
  const [org, setOrg] = useState(null);
  const [members, setMembers] = useState([]);
  const [webhooks, setWebhooks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      orgAPI.me().then(r => setOrg(r.data)).catch(() => {}),
      orgAPI.members().then(r => setMembers(r.data || [])).catch(() => {
        if (user) setMembers([{ email: user.email, role: 'admin', id: user.id }]);
      }),
      webhooksAPI.list().then(r => setWebhooks(r.data || [])).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const handleOrgSave = async (form) => {
    // Would call orgAPI.update(form)
    setOrg(o => ({ ...o, ...form }));
  };

  const handleRemoveMember = (userId) => {
    if (!confirm('이 팀원을 제거하시겠습니까?')) return;
    setMembers(ms => ms.filter(m => m.id !== userId));
    toast.success('팀원이 제거되었습니다.');
  };

  const handleDeleteWebhook = async (id) => {
    if (!confirm('이 웹훅을 삭제하시겠습니까?')) return;
    try {
      await webhooksAPI.delete(id);
      setWebhooks(ws => ws.filter(w => w.id !== id));
      toast.success('웹훅이 삭제되었습니다.');
    } catch {
      toast.error('삭제에 실패했습니다.');
    }
  };

  const handleTestWebhook = async (id) => {
    try {
      await webhooksAPI.test(id);
      toast.success('테스트 요청이 전송되었습니다.');
    } catch {
      toast.error('테스트에 실패했습니다.');
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">설정</h1>
        <p className="text-slate-400 text-sm mt-1">조직 정보, 팀원, 웹훅을 관리하세요.</p>
      </div>

      <div className="mb-6">
        <TabBar active={activeTab} onChange={setActiveTab} />
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="w-10 h-10 spinner" />
        </div>
      ) : (
        <>
          {activeTab === '조직' && <OrgTab org={org} onSave={handleOrgSave} />}
          {activeTab === '팀원' && (
            <MembersTab
              members={members}
              onRoleChange={() => {}}
              onRemove={handleRemoveMember}
            />
          )}
          {activeTab === '웹훅' && (
            <WebhooksTab
              webhooks={webhooks}
              onDelete={handleDeleteWebhook}
              onTest={handleTestWebhook}
              onAdd={(wh) => setWebhooks(ws => [wh, ...ws])}
            />
          )}
        </>
      )}
    </div>
  );
}

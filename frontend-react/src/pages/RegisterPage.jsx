import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Leaf, Mail, Lock, Building2, ArrowRight, Eye, EyeOff, CheckCircle, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { authAPI } from '../api/client';
import toast from 'react-hot-toast';

export default function RegisterPage() {
  const [form, setForm] = useState({ email: '', password: '', confirmPassword: '', org_name: '' });
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  const passwordStrength = () => {
    const p = form.password;
    if (!p) return 0;
    let s = 0;
    if (p.length >= 8) s++;
    if (/[A-Z]/.test(p)) s++;
    if (/[0-9]/.test(p)) s++;
    if (/[^A-Za-z0-9]/.test(p)) s++;
    return s;
  };

  const strengthLabel = ['', '약함', '보통', '강함', '매우 강함'];
  const strengthColor = ['', 'bg-red-500', 'bg-amber-500', 'bg-sky-500', 'bg-emerald-500'];
  const ps = passwordStrength();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.email || !form.password || !form.org_name) {
      toast.error('모든 필드를 입력해주세요.');
      return;
    }
    if (form.password !== form.confirmPassword) {
      toast.error('비밀번호가 일치하지 않습니다.');
      return;
    }
    if (form.password.length < 8) {
      toast.error('비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    setLoading(true);
    try {
      await authAPI.register(form.email, form.password, form.org_name);
      toast.success('계정이 생성되었습니다!');
      await login(form.email, form.password);
      navigate('/dashboard');
    } catch (err) {
      const msg = err.response?.data?.detail || '회원가입에 실패했습니다.';
      toast.error(Array.isArray(msg) ? msg[0]?.msg || '오류가 발생했습니다.' : msg);
    } finally {
      setLoading(false);
    }
  };

  const benefits = [
    '14일 무료 체험',
    'EUDR 규정 준수 자동화',
    '위성 기반 AI 분석',
    '신용카드 불필요',
  ];

  return (
    <div className="min-h-screen flex" style={{ background: '#0f172a' }}>
      {/* Left: Brand Panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden"
        style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%)' }}>
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/3 left-1/3 w-72 h-72 rounded-full opacity-15 blur-3xl"
            style={{ background: 'radial-gradient(circle, #0ea5e9, transparent)' }} />
          <div className="absolute bottom-1/4 right-1/4 w-56 h-56 rounded-full opacity-10 blur-3xl"
            style={{ background: 'radial-gradient(circle, #10b981, transparent)' }} />
        </div>

        <div className="relative">
          <Link to="/" className="flex items-center gap-2 w-fit">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-sky-500 flex items-center justify-center">
              <Leaf className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-xl text-white">TraceCheck</span>
          </Link>
        </div>

        <div className="relative">
          <h2 className="text-4xl font-bold text-white mb-4 leading-tight">
            오늘부터 시작하는<br />
            <span className="gradient-text">공급망 ESG 혁신</span>
          </h2>
          <p className="text-slate-400 mb-10 leading-relaxed">
            14일 무료 체험으로 TraceCheck의 모든 기능을 경험하세요.<br />
            EUDR 준수를 위한 첫 분석까지 단 10분이면 충분합니다.
          </p>
          <div className="space-y-3">
            {benefits.map((b, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <span className="text-slate-300 text-sm">{b}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="relative glass rounded-2xl p-5">
          <div className="text-xs text-slate-500 uppercase tracking-widest mb-2">빠른 시작</div>
          <div className="flex items-center gap-3">
            <div className="flex -space-x-2">
              {['K', 'L', 'P'].map((c, i) => (
                <div key={i} className="w-8 h-8 rounded-full border-2 border-slate-800 flex items-center justify-center text-xs font-bold text-white"
                  style={{ background: ['#10b981', '#0ea5e9', '#8b5cf6'][i] }}>
                  {c}
                </div>
              ))}
            </div>
            <div>
              <div className="text-white text-sm font-medium">첫 분석까지 5분</div>
              <div className="text-slate-400 text-xs">CSV 업로드 한 번으로 바로 시작하세요</div>
            </div>
          </div>
        </div>
      </div>

      {/* Right: Register Form */}
      <div className="flex-1 flex items-center justify-center p-6 overflow-y-auto">
        <div className="w-full max-w-md py-8">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-sky-500 flex items-center justify-center">
              <Leaf className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-xl text-white">TraceCheck</span>
          </div>

          <h1 className="text-2xl font-bold text-white mb-1">무료 계정 만들기</h1>
          <p className="text-slate-400 text-sm mb-8">14일 무료 체험 · 신용카드 불필요</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">조직명</label>
              <div className="relative">
                <Building2 className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type="text"
                  className="form-input pl-10"
                  placeholder="회사명 또는 팀명"
                  value={form.org_name}
                  onChange={set('org_name')}
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">업무용 이메일</label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type="email"
                  className="form-input pl-10"
                  placeholder="you@company.com"
                  value={form.email}
                  onChange={set('email')}
                  autoComplete="email"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">비밀번호</label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type={showPw ? 'text' : 'password'}
                  className="form-input pl-10 pr-10"
                  placeholder="8자 이상"
                  value={form.password}
                  onChange={set('password')}
                  autoComplete="new-password"
                  required
                />
                <button
                  type="button"
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                  onClick={() => setShowPw(!showPw)}
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {form.password && (
                <div className="mt-2">
                  <div className="flex gap-1 mb-1">
                    {[1,2,3,4].map(i => (
                      <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${i <= ps ? strengthColor[ps] : 'bg-white/10'}`} />
                    ))}
                  </div>
                  <span className="text-xs text-slate-500">보안 강도: <span className={`font-medium ${ps >= 3 ? 'text-emerald-400' : ps >= 2 ? 'text-sky-400' : 'text-amber-400'}`}>{strengthLabel[ps]}</span></span>
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">비밀번호 확인</label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type={showPw ? 'text' : 'password'}
                  className="form-input pl-10"
                  placeholder="비밀번호 재입력"
                  value={form.confirmPassword}
                  onChange={set('confirmPassword')}
                  autoComplete="new-password"
                  required
                />
                {form.confirmPassword && (
                  <div className="absolute right-3.5 top-1/2 -translate-y-1/2">
                    {form.password === form.confirmPassword
                      ? <CheckCircle className="w-4 h-4 text-emerald-400" />
                      : <div className="w-4 h-4 rounded-full bg-red-500/30 border border-red-500/50" />}
                  </div>
                )}
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 rounded-xl justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 spinner" />
                  계정 생성 중...
                </>
              ) : (
                <>
                  무료 계정 만들기 <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-6">
            이미 계정이 있으신가요?{' '}
            <Link to="/login" className="text-emerald-400 hover:text-emerald-300 font-medium transition-colors">
              로그인
            </Link>
          </p>

          <div className="mt-6 pt-6 border-t border-white/5 text-center">
            <p className="text-xs text-slate-600">
              계정 생성 시 <a href="#" className="text-slate-500 hover:text-slate-400">이용약관</a> 및{' '}
              <a href="#" className="text-slate-500 hover:text-slate-400">개인정보처리방침</a>에 동의하게 됩니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

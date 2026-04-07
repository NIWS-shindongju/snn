import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Leaf, Mail, Lock, ArrowRight, Eye, EyeOff, Shield, BarChart3, CheckCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmedEmail = email.trim();
    const trimmedPassword = password.trim();
    if (!trimmedEmail || !trimmedPassword) {
      toast.error('이메일과 비밀번호를 입력해주세요.');
      return;
    }
    setLoading(true);
    try {
      await login(trimmedEmail, trimmedPassword);
      toast.success('로그인 성공!');
      navigate('/dashboard');
    } catch (err) {
      const msg = err.response?.data?.detail || '로그인에 실패했습니다.';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const stats = [
    { icon: <BarChart3 className="w-5 h-5" />, value: '1,200+', label: '기업 고객' },
    { icon: <Shield className="w-5 h-5" />, value: '98%', label: 'EUDR 통과율' },
    { icon: <CheckCircle className="w-5 h-5" />, value: '50만+', label: '분석 필지' },
  ];

  return (
    <div className="min-h-screen flex" style={{ background: '#0f172a' }}>
      {/* Left: Brand Panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden"
        style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%)' }}>
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-64 h-64 rounded-full opacity-15 blur-3xl"
            style={{ background: 'radial-gradient(circle, #10b981, transparent)' }} />
          <div className="absolute bottom-1/4 right-1/4 w-56 h-56 rounded-full opacity-10 blur-3xl"
            style={{ background: 'radial-gradient(circle, #0ea5e9, transparent)' }} />
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
            공급망 ESG 관리를<br />
            <span className="gradient-text">더 스마트하게</span>
          </h2>
          <p className="text-slate-400 mb-10 leading-relaxed">
            EUDR 규정 준수부터 탄소발자국 추적까지.<br />
            AI 기반 위성 분석으로 공급망 리스크를 선제적으로 차단합니다.
          </p>
          <div className="grid grid-cols-3 gap-4">
            {stats.map((s, i) => (
              <div key={i} className="glass rounded-xl p-4 text-center">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto mb-2">
                  {s.icon}
                </div>
                <div className="font-bold text-white text-lg">{s.value}</div>
                <div className="text-slate-500 text-xs mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative">
          <div className="glass rounded-2xl p-5">
            <div className="flex gap-1 mb-3">
              {[1,2,3,4,5].map(i => <div key={i} className="w-4 h-4 text-amber-400">★</div>)}
            </div>
            <p className="text-slate-300 text-sm leading-relaxed mb-3">
              "EUDR 대응에 필요한 모든 것을 한 플랫폼에서 해결할 수 있어 놀랐습니다."
            </p>
            <div className="text-slate-400 text-xs">— 김민준 ESG팀장, 코스피 식품기업</div>
          </div>
        </div>
      </div>

      {/* Right: Login Form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-sky-500 flex items-center justify-center">
              <Leaf className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-xl text-white">TraceCheck</span>
          </div>

          <h1 className="text-2xl font-bold text-white mb-1">다시 오셨군요! 👋</h1>
          <p className="text-slate-400 text-sm mb-8">계정에 로그인하여 공급망 분석을 시작하세요.</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">이메일</label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type="email"
                  className="form-input pl-10"
                  placeholder="you@company.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
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
                  placeholder="비밀번호 입력"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete="current-password"
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
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="w-4 h-4 rounded border-white/20 bg-white/5 text-emerald-500" />
                <span className="text-sm text-slate-400">로그인 상태 유지</span>
              </label>
              <a href="#" className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors">
                비밀번호 찾기
              </a>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 rounded-xl justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 spinner" />
                  로그인 중...
                </>
              ) : (
                <>
                  로그인 <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-6">
            계정이 없으신가요?{' '}
            <Link to="/register" className="text-emerald-400 hover:text-emerald-300 font-medium transition-colors">
              무료로 시작하기
            </Link>
          </p>

          <div className="mt-8 pt-6 border-t border-white/5 text-center">
            <p className="text-xs text-slate-600">
              로그인 시 <a href="#" className="text-slate-500 hover:text-slate-400">이용약관</a> 및{' '}
              <a href="#" className="text-slate-500 hover:text-slate-400">개인정보처리방침</a>에 동의하게 됩니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

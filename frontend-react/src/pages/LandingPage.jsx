import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Shield, Leaf, BarChart3, FileCheck, Globe, ArrowRight, Check,
  ChevronDown, ChevronUp, Star, Zap, Lock, Users, TrendingUp,
  AlertTriangle, CheckCircle, Building2, Menu, X
} from 'lucide-react';
import { useCountUp, useScrollReveal } from '../hooks/useCountUp';

function StatCard({ value, suffix, label, prefix }) {
  const { count, ref } = useCountUp(value, 2000);
  return (
    <div ref={ref} className="text-center">
      <div className="text-4xl font-bold text-white mb-1">
        {prefix && <span className="gradient-text">{prefix}</span>}
        <span className="gradient-text">{count.toLocaleString()}</span>
        {suffix && <span className="gradient-text">{suffix}</span>}
      </div>
      <div className="text-slate-400 text-sm">{label}</div>
    </div>
  );
}

function FAQItem({ q, a }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-white/10 rounded-xl overflow-hidden">
      <button
        className="w-full flex items-center justify-between p-5 text-left hover:bg-white/5 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span className="font-medium text-slate-200">{q}</span>
        {open ? <ChevronUp className="w-5 h-5 text-emerald-500 flex-shrink-0" /> : <ChevronDown className="w-5 h-5 text-slate-400 flex-shrink-0" />}
      </button>
      {open && (
        <div className="px-5 pb-5 text-slate-400 text-sm leading-relaxed border-t border-white/5">
          {a}
        </div>
      )}
    </div>
  );
}

export default function LandingPage() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const heroReveal = useScrollReveal();
  const featuresReveal = useScrollReveal();
  const howReveal = useScrollReveal();

  const features = [
    {
      icon: <Leaf className="w-6 h-6" />,
      title: '위성 기반 사전 스크리닝',
      desc: 'Sentinel-2 위성 데이터로 농장·필지의 식생 변화를 자동 분석합니다. HIGH 등급 필지를 사전 식별하여 현장 실사 대상을 효율적으로 선별하세요.',
      color: 'text-emerald-400',
      bg: 'bg-emerald-500/10',
    },
    {
      icon: <Shield className="w-6 h-6" />,
      title: '3단계 리스크 등급 분류',
      desc: '필지별 HIGH/REVIEW/LOW 등급으로 분류하여 우선순위를 시각화합니다. HIGH 등급 필지는 현장 실사 병행을 권고합니다.',
      color: 'text-sky-400',
      bg: 'bg-sky-500/10',
    },
    {
      icon: <BarChart3 className="w-6 h-6" />,
      title: '실시간 분석 대시보드',
      desc: '필지별 위성 이미지 분석, 트렌드 차트, 지역별 히트맵으로 경영진 보고서를 원클릭 생성.',
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
    },
    {
      icon: <FileCheck className="w-6 h-6" />,
      title: '규정 준수 증빙 관리',
      desc: 'PDF/CSV/JSON 형식의 감사 이력과 DDS(Due Diligence Statement) 자동 생성으로 당국 제출 준비 완료.',
      color: 'text-amber-400',
      bg: 'bg-amber-500/10',
    },
  ];

  const steps = [
    { n: '01', title: '프로젝트 생성', desc: '공급망 이름과 대상 국가를 설정합니다.' },
    { n: '02', title: '필지 데이터 업로드', desc: 'CSV/GeoJSON 형식으로 농장·필지 좌표를 업로드합니다.' },
    { n: '03', title: 'AI 분석 실행', desc: '위성 이미지와 AI 모델로 삼림 변화를 자동 분석합니다.' },
    { n: '04', title: '보고서 다운로드', desc: 'EUDR 규정 준수 증빙 보고서를 즉시 다운로드합니다.' },
  ];

  const plans = [
    {
      name: 'Free',
      price: '0',
      period: '/월',
      desc: '소규모 팀을 위한 시작 플랜',
      color: 'border-white/10',
      badge: null,
      features: ['프로젝트 3개', '필지 100개/월', 'PDF 보고서', '이메일 지원', '1년 이력 보관'],
    },
    {
      name: 'Pro',
      price: '490,000',
      period: '/월',
      desc: '성장하는 기업을 위한 전문 플랜',
      color: 'border-emerald-500/50',
      badge: '인기',
      highlight: true,
      features: ['프로젝트 무제한', '필지 10,000개/월', 'PDF/CSV/JSON 보고서', 'REST API 접근', '우선 지원', '5년 감사 아카이브 (EUDR 준수)', '팀원 10명'],
    },
    {
      name: 'Enterprise',
      price: '문의',
      period: '',
      desc: '대규모 공급망 맞춤 솔루션',
      color: 'border-sky-500/50',
      badge: null,
      features: ['모든 Pro 기능', '필지 무제한', '전용 인프라 (데이터 격리)', 'SLA 99.9%', '전담 CSM 매니저', 'SAP/Oracle ERP 연동', 'SSO/SAML 인증', '무제한 팀원', '10년 감사 아카이브'],
    },
  ];

  const reviews = [
    { name: '김민준', role: 'ESG팀장, 식품 수출기업 (파일럿 고객)', text: 'EUDR 대응 준비를 6개월에서 3주로 단축했습니다. 공급망 필지의 위험 등급을 한눈에 파악할 수 있어 감사 대응 준비가 훨씬 간편해졌습니다.', stars: 5 },
    { name: '이서연', role: '지속가능경영팀, 유통사 (파일럿 고객)', text: '위성 데이터 기반 사전 스크리닝으로 현장 실사 대상을 사전 선별할 수 있었습니다. 다만 HIGH 등급 필지는 반드시 현장 확인과 병행하는 것을 권장합니다.', stars: 5 },
    { name: 'Thomas K.', role: 'Compliance Manager, EU Importer (Pilot)', text: 'The automated DDS generation saved our legal team significant time. We use TraceCheck as a first-pass screening tool alongside our existing due diligence process.', stars: 5 },
  ];

  const faqs = [
    { q: 'EUDR 규정에 어떻게 대응하나요?', a: 'TraceCheck는 EU 삼림벌채방지법(EUDR)이 요구하는 Due Diligence Statement(DDS) 자동 생성, 공급망 트레이서빌리티, 지리적 위치 증빙을 모두 지원합니다. 위성 이미지 분석으로 2020년 12월 31일 이후 삼림 변화를 감지하여 적합성 여부를 판단합니다.' },
    { q: '어떤 데이터 형식을 지원하나요?', a: 'CSV, GeoJSON, Shapefile 등 주요 지리정보 형식을 지원합니다. 최소 위도/경도 좌표만 있으면 분석이 가능하며, 폴리곤 데이터를 사용하면 더욱 정밀한 분석이 가능합니다.' },
    { q: '분석에 얼마나 걸리나요?', a: '필지 수에 따라 다르지만 100개 필지 기준 약 2-5분, 1,000개 필지 기준 약 15-30분이 소요됩니다. 분석 완료 시 이메일과 웹훅으로 알림을 받을 수 있습니다.' },
    { q: '데이터 보안은 어떻게 보장되나요?', a: '모든 데이터는 AES-256으로 암호화되어 저장되며, 전송 시 TLS 1.3을 적용합니다. SOC 2 Type II 및 ISO 27001 인증을 준비 중이며(2026 하반기 목표), Enterprise 플랜은 전용 인프라와 유럽 데이터 서버(GDPR 준수) 옵션을 제공합니다.' },
    { q: '위성 분석만으로 EUDR 준수가 가능한가요?', a: 'TraceCheck의 위성 분석은 공급망 리스크를 사전 스크리닝하는 도구입니다. HIGH 등급 필지에 대해서는 반드시 현장 실사(ground-truthing)를 병행할 것을 권장합니다. 구름, 계절 변화, 자연재해 등으로 인한 오탐(false positive) 가능성이 있으며, 최종 실사 판단은 담당자의 검증이 필요합니다. TraceCheck는 이 과정을 효율화하는 도구이지, 대체하는 도구가 아닙니다.' },
    { q: 'API 통합이 가능한가요?', a: 'Pro 플랜부터 REST API를 제공합니다. Python, JavaScript SDK를 지원하며, 웹훅으로 분석 완료 이벤트를 실시간 수신할 수 있습니다. Enterprise 플랜에서는 SAP, Oracle 등 ERP/SCM 시스템 연동을 지원합니다.' },
  ];

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* Navbar */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/5" style={{ background: 'rgba(15,23,42,0.85)', backdropFilter: 'blur(12px)' }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-sky-500 flex items-center justify-center">
                <Leaf className="w-4 h-4 text-white" />
              </div>
              <span className="font-bold text-lg text-white">TraceCheck</span>
            </div>
            <div className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-sm text-slate-400 hover:text-white transition-colors">기능</a>
              <a href="#how" className="text-sm text-slate-400 hover:text-white transition-colors">작동 방식</a>
              <a href="#pricing" className="text-sm text-slate-400 hover:text-white transition-colors">가격</a>
              <a href="#faq" className="text-sm text-slate-400 hover:text-white transition-colors">FAQ</a>
            </div>
            <div className="hidden md:flex items-center gap-3">
              <Link to="/login" className="text-sm text-slate-300 hover:text-white px-4 py-2 rounded-lg transition-colors">
                로그인
              </Link>
              <Link to="/register" className="btn-primary text-sm px-5 py-2 rounded-lg">
                무료 시작 <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
            <button className="md:hidden text-slate-400" onClick={() => setMobileOpen(!mobileOpen)}>
              {mobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
        {mobileOpen && (
          <div className="md:hidden border-t border-white/5 px-4 py-4 flex flex-col gap-3" style={{ background: 'rgba(15,23,42,0.98)' }}>
            <a href="#features" className="text-sm text-slate-300 py-2" onClick={() => setMobileOpen(false)}>기능</a>
            <a href="#how" className="text-sm text-slate-300 py-2" onClick={() => setMobileOpen(false)}>작동 방식</a>
            <a href="#pricing" className="text-sm text-slate-300 py-2" onClick={() => setMobileOpen(false)}>가격</a>
            <a href="#faq" className="text-sm text-slate-300 py-2" onClick={() => setMobileOpen(false)}>FAQ</a>
            <div className="flex flex-col gap-2 pt-2 border-t border-white/10">
              <Link to="/login" className="btn-secondary text-sm py-3 justify-center rounded-lg">로그인</Link>
              <Link to="/register" className="btn-primary text-sm py-3 justify-center rounded-lg">무료 시작</Link>
            </div>
          </div>
        )}
      </nav>

      {/* Hero */}
      <section className="hero-gradient pt-32 pb-24 px-4 relative overflow-hidden">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-20 left-1/4 w-96 h-96 rounded-full opacity-10 blur-3xl" style={{ background: 'radial-gradient(circle, #10b981, transparent)' }} />
          <div className="absolute bottom-20 right-1/4 w-80 h-80 rounded-full opacity-10 blur-3xl" style={{ background: 'radial-gradient(circle, #0ea5e9, transparent)' }} />
        </div>
        <div className="max-w-5xl mx-auto text-center relative">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium mb-8 glass border border-emerald-500/30 text-emerald-400">
            <Zap className="w-3 h-3" />
            한국 기업을 위한 EUDR 대응 솔루션
          </div>
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold text-white mb-6 leading-tight">
            EUDR 시행까지<br />
            <span className="gradient-text">9개월, 지금 시작하세요</span>
          </h1>
          <p className="text-xl text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed">
            CSV 업로드 한 번으로 공급망 필지의 삼림 벌채 위험을 사전 스크리닝합니다.
            한국어 UI · 원화 결제 · 5분 만에 첫 분석 결과를 확인하세요.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
            <Link to="/register" className="btn-primary text-base px-8 py-4 rounded-xl">
              무료로 시작하기 <ArrowRight className="w-5 h-5" />
            </Link>
            <a href="#how" className="btn-secondary text-base px-8 py-4 rounded-xl">
              작동 방식 보기
            </a>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 pt-12 border-t border-white/10">
            <StatCard value={5} suffix="분" label="첫 분석까지" />
            <StatCard value={490} suffix="만원" prefix="월 " label="Pro 플랜" />
            <StatCard value={9} suffix="개월" label="EUDR 시행까지" />
            <StatCard value={7} suffix="종" label="대상 원자재" />
          </div>
        </div>
      </section>

      {/* Trust badges */}
      <section className="py-10 border-y border-white/5 bg-slate-900/50">
        <div className="max-w-5xl mx-auto px-4">
          <div className="flex flex-wrap justify-center gap-8 items-center">
            <div className="flex items-center gap-3">
              <Lock className="w-4 h-4 text-slate-500" />
              <span className="text-slate-400 text-sm">AES-256 암호화</span>
            </div>
            <div className="flex items-center gap-3">
              <Shield className="w-4 h-4 text-slate-500" />
              <span className="text-slate-400 text-sm">TLS 1.3 전송 보안</span>
            </div>
            <div className="flex items-center gap-3">
              <Globe className="w-4 h-4 text-slate-500" />
              <span className="text-slate-400 text-sm">EU 데이터 서버 옵션</span>
            </div>
            <div className="flex items-center gap-3">
              <CheckCircle className="w-4 h-4 text-amber-500" />
              <span className="text-slate-400 text-sm">ISO 27001 · SOC 2 인증 준비 중</span>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16" ref={featuresReveal.ref}>
            <div className="text-emerald-400 text-sm font-semibold uppercase tracking-widest mb-3">핵심 기능</div>
            <h2 className="text-4xl font-bold text-white mb-4">ESG 공급망 관리의 새로운 기준</h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              복잡한 글로벌 공급망의 환경 리스크를 데이터 기반으로 관리하고, 규제 당국에 신뢰할 수 있는 증빙을 제출하세요.
            </p>
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            {features.map((f, i) => (
              <div key={i} className="glass rounded-2xl p-6 card-hover">
                <div className={`w-12 h-12 rounded-xl ${f.bg} ${f.color} flex items-center justify-center mb-4`}>
                  {f.icon}
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{f.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="py-24 px-4 bg-slate-800/30">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <div className="text-sky-400 text-sm font-semibold uppercase tracking-widest mb-3">작동 방식</div>
            <h2 className="text-4xl font-bold text-white mb-4">4단계로 완성하는 EUDR 준수</h2>
          </div>
          <div className="grid md:grid-cols-4 gap-6">
            {steps.map((s, i) => (
              <div key={i} className="relative text-center">
                {i < 3 && <div className="hidden md:block absolute top-8 left-1/2 w-full h-px" style={{ background: 'linear-gradient(90deg, #10b981, transparent)' }} />}
                <div className="relative w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center font-bold text-lg"
                  style={{ background: 'linear-gradient(135deg, rgba(16,185,129,0.2), rgba(14,165,233,0.2))', border: '1px solid rgba(16,185,129,0.3)', color: '#10b981' }}>
                  {s.n}
                </div>
                <h3 className="font-semibold text-white mb-2 text-sm">{s.title}</h3>
                <p className="text-slate-400 text-xs leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 px-4">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <div className="text-emerald-400 text-sm font-semibold uppercase tracking-widest mb-3">가격</div>
            <h2 className="text-4xl font-bold text-white mb-4">규모에 맞는 플랜 선택</h2>
            <p className="text-slate-400">모든 플랜 14일 무료 체험 가능 · 신용카드 불필요</p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {plans.map((p, i) => (
              <div key={i} className={`rounded-2xl p-6 border ${p.color} relative ${p.highlight ? 'bg-gradient-to-b from-emerald-950/50 to-slate-900' : 'glass'}`}>
                {p.badge && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full text-xs font-bold"
                    style={{ background: 'linear-gradient(90deg, #10b981, #059669)', color: 'white' }}>
                    {p.badge}
                  </div>
                )}
                <div className="mb-6">
                  <div className="text-slate-400 text-sm font-medium mb-1">{p.name}</div>
                  <div className="flex items-end gap-1 mb-2">
                    {p.price === '문의' ? (
                      <span className="text-3xl font-bold text-white">문의</span>
                    ) : (
                      <>
                        <span className="text-sm text-slate-400 mt-2">₩</span>
                        <span className="text-3xl font-bold text-white">{p.price}</span>
                        <span className="text-slate-400 text-sm mb-1">{p.period}</span>
                      </>
                    )}
                  </div>
                  <p className="text-slate-400 text-xs">{p.desc}</p>
                </div>
                <ul className="space-y-3 mb-8">
                  {p.features.map((f, j) => (
                    <li key={j} className="flex items-center gap-2 text-sm text-slate-300">
                      <CheckCircle className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Link to="/register"
                  className={`block text-center py-3 rounded-xl font-semibold text-sm transition-all ${p.highlight ? 'btn-primary' : 'btn-secondary'}`}>
                  {p.price === '문의' ? '영업팀 연락' : '시작하기'}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Reviews */}
      <section className="py-24 px-4 bg-slate-800/30">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <div className="text-sky-400 text-sm font-semibold uppercase tracking-widest mb-3">고객 후기</div>
            <h2 className="text-4xl font-bold text-white mb-4">실제 사용 고객들의 이야기</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {reviews.map((r, i) => (
              <div key={i} className="glass rounded-2xl p-6">
                <div className="flex gap-1 mb-4">
                  {Array(r.stars).fill(0).map((_, j) => (
                    <Star key={j} className="w-4 h-4 text-amber-400 fill-amber-400" />
                  ))}
                </div>
                <p className="text-slate-300 text-sm leading-relaxed mb-6">"{r.text}"</p>
                <div>
                  <div className="font-semibold text-white text-sm">{r.name}</div>
                  <div className="text-slate-500 text-xs mt-1">{r.role}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-24 px-4">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-16">
            <div className="text-emerald-400 text-sm font-semibold uppercase tracking-widest mb-3">FAQ</div>
            <h2 className="text-4xl font-bold text-white mb-4">자주 묻는 질문</h2>
          </div>
          <div className="space-y-3">
            {faqs.map((f, i) => <FAQItem key={i} {...f} />)}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <div className="rounded-3xl p-12 relative overflow-hidden"
            style={{ background: 'linear-gradient(135deg, rgba(16,185,129,0.15), rgba(14,165,233,0.1))', border: '1px solid rgba(16,185,129,0.2)' }}>
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-64 rounded-full opacity-20 blur-3xl" style={{ background: 'radial-gradient(circle, #10b981, transparent)' }} />
            </div>
            <Globe className="w-12 h-12 mx-auto text-emerald-400 mb-6" />
            <h2 className="text-4xl font-bold text-white mb-4">지금 바로 시작하세요</h2>
            <p className="text-slate-400 mb-8 max-w-xl mx-auto">
              14일 무료 체험으로 EUDR 공급망 분석을 경험해보세요. 신용카드 없이도 시작 가능합니다.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link to="/register" className="btn-primary text-base px-8 py-4 rounded-xl">
                무료 계정 만들기 <ArrowRight className="w-5 h-5" />
              </Link>
              <Link to="/login" className="btn-secondary text-base px-8 py-4 rounded-xl">
                기존 계정 로그인
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-12 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-sky-500 flex items-center justify-center">
                <Leaf className="w-4 h-4 text-white" />
              </div>
              <span className="font-bold text-white">TraceCheck</span>
            </div>
            <div className="flex gap-6 text-sm text-slate-500">
              <a href="#" className="hover:text-slate-300 transition-colors">이용약관</a>
              <a href="#" className="hover:text-slate-300 transition-colors">개인정보처리방침</a>
              <a href="#" className="hover:text-slate-300 transition-colors">쿠키 정책</a>
              <a href="mailto:support@tracecheck.io" className="hover:text-slate-300 transition-colors">문의</a>
            </div>
            <div className="text-slate-600 text-sm">© 2025 TraceCheck. All rights reserved.</div>
          </div>
        </div>
      </footer>
    </div>
  );
}

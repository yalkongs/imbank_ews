import React, { useState, useEffect } from 'react';
import { Users, TrendingDown, CheckCircle2, AlertTriangle, X, ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { rmApi, ewsActionApi, companyApi, ewsApi } from '../utils/api';
import { LineChart, Line, XAxis as RXAxis, YAxis as RYAxis, CartesianGrid as RGrid, Tooltip as RTooltip, ResponsiveContainer as RRC } from 'recharts';
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Legend
} from 'recharts';

const GRADE_COLORS_PIE: Record<string, string> = {
  A: '#16a34a', B: '#eab308', C: '#f97316', D: '#dc2626',
};
const GRADE_BADGE: Record<string, string> = {
  A: 'bg-green-100 text-green-700',
  B: 'bg-yellow-100 text-yellow-700',
  C: 'bg-orange-100 text-orange-700',
  D: 'bg-red-100 text-red-700',
};
const STATUS_BADGE: Record<string, string> = {
  OPEN: 'bg-gray-100 text-gray-700',
  IN_PROGRESS: 'bg-blue-100 text-blue-700',
  COMPLETED: 'bg-green-100 text-green-700',
  WAIVED: 'bg-yellow-100 text-yellow-700',
};
const STATUS_LABEL: Record<string, string> = {
  OPEN: '대기', IN_PROGRESS: '진행중', COMPLETED: '완료', WAIVED: '면제',
};

/* ── 기업 상세 미니 모달 ── */
function CompanyMiniModal({ borrowerId, onClose }: { borrowerId: string; onClose: () => void }) {
  const navigate = useNavigate();
  const [detail, setDetail] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      companyApi.getById(borrowerId),
      ewsApi.getCompanyHistory(borrowerId),
    ]).then(([d, h]) => {
      setDetail(d.data);
      setHistory(h.data || []);
      setLoading(false);
    });
  }, [borrowerId]);

  const profile = detail?.profile;
  const latestEws = history.length > 0 ? history[history.length - 1] : null;
  const gradeColor: Record<string, string> = {
    A: 'bg-green-100 text-green-700', B: 'bg-yellow-100 text-yellow-700',
    C: 'bg-orange-100 text-orange-700', D: 'bg-red-100 text-red-700',
  };
  const scoreData = history.map((h: any) => ({
    label: `${String(h.ym).slice(2, 4)}-${String(h.ym).slice(4)}`,
    score: h.ews_score,
  }));

  return (
    <div className="fixed inset-0 bg-black/40 flex items-start justify-end z-50" onClick={onClose}>
      <div
        className="bg-white h-full w-full max-w-xl shadow-2xl flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <div>
            <p className="text-xs text-gray-400 mb-0.5">기업 상세 (미리보기)</p>
            <h3 className="text-base font-bold text-gray-900">{profile?.company_name || '로딩 중...'}</h3>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(`/companies?id=${borrowerId}`)}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 border border-blue-200 px-2 py-1 rounded-lg"
            >
              <ExternalLink size={12} />
              전체 상세
            </button>
            <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg">
              <X size={16} className="text-gray-500" />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* 기본 정보 */}
            {profile && (
              <div className="flex items-start justify-between">
                <div className="space-y-1 text-sm">
                  <div className="flex gap-4">
                    <span className="text-gray-500">규모: <strong>{profile.firm_size_cd}</strong></span>
                    <span className="text-gray-500">업종: <strong>{profile.industry_cd}</strong></span>
                    <span className="text-gray-500">상장: <strong>{profile.listed_flag ? 'Y' : 'N'}</strong></span>
                  </div>
                  {profile.default_ym && (
                    <p className="text-red-600 text-xs font-medium">부도월: {profile.default_ym}</p>
                  )}
                </div>
                {latestEws && (
                  <div className="text-right">
                    <span className={`px-3 py-1 rounded-full text-sm font-bold ${gradeColor[latestEws.ews_grade] || ''}`}>
                      EWS {latestEws.ews_grade}
                    </span>
                    <p className="text-xs text-gray-400 mt-1">점수: {latestEws.ews_score?.toFixed(1)}</p>
                  </div>
                )}
              </div>
            )}

            {/* EWS 점수 추이 */}
            <div>
              <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">EWS 점수 추이</p>
              <RRC width="100%" height={160}>
                <LineChart data={scoreData}>
                  <RGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <RXAxis dataKey="label" tick={{ fontSize: 10 }} interval={5} />
                  <RYAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <RTooltip />
                  <Line type="monotone" dataKey="score" stroke="#e74c3c" dot={false} strokeWidth={2} />
                </LineChart>
              </RRC>
            </div>

            {/* 여신 현황 */}
            {detail?.facilities?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">여신 현황</p>
                <table className="w-full text-xs border border-gray-100 rounded-lg overflow-hidden">
                  <thead className="bg-gray-50">
                    <tr>
                      {['유형', '약정(억)', '잔액(억)', '금리', '만기'].map(h => (
                        <th key={h} className="px-2 py-1.5 text-left text-gray-500">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {detail.facilities.map((f: any) => (
                      <tr key={f.facility_id} className="border-t border-gray-100">
                        <td className="px-2 py-1.5 text-gray-700">{f.facility_type}</td>
                        <td className="px-2 py-1.5 text-right font-mono">{f.committed_amount_억?.toFixed(1)}</td>
                        <td className="px-2 py-1.5 text-right font-mono">{f.outstanding_amount_억?.toFixed(1)}</td>
                        <td className="px-2 py-1.5 text-right">{(f.interest_rate * 100).toFixed(2)}%</td>
                        <td className="px-2 py-1.5 text-right text-gray-500">{f.maturity_ym}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* 최신 EWS 신호 (최근 6개월) */}
            {history.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">최근 EWS 신호 (최신 6개월)</p>
                <table className="w-full text-xs border border-gray-100 rounded-lg overflow-hidden">
                  <thead className="bg-gray-50">
                    <tr>
                      {['기준월', '등급', 'EWS점수', 'Stage', '연체일'].map(h => (
                        <th key={h} className="px-2 py-1.5 text-left text-gray-500">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...history].reverse().slice(0, 6).map((h: any) => (
                      <tr key={h.ym} className="border-t border-gray-100">
                        <td className="px-2 py-1.5 text-gray-600">{h.ym}</td>
                        <td className="px-2 py-1.5">
                          <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${gradeColor[h.ews_grade] || ''}`}>{h.ews_grade}</span>
                        </td>
                        <td className="px-2 py-1.5 font-mono">{h.ews_score?.toFixed(1)}</td>
                        <td className="px-2 py-1.5 text-center">{h.ifrs9_stage}</td>
                        <td className={`px-2 py-1.5 text-right ${h.principal_past_due_days > 30 ? 'text-red-600 font-semibold' : 'text-gray-600'}`}>
                          {h.principal_past_due_days}일
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function RMPortfolio() {
  const [rmList, setRmList]   = useState<any[]>([]);
  const [selectedRm, setSelectedRm] = useState<string>('');
  const [summary, setSummary] = useState<any>(null);
  const [portfolio, setPortfolio] = useState<any[]>([]);
  const [actions, setActions] = useState<any[]>([]);
  const [comparison, setComparison] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'portfolio' | 'actions' | 'compare'>('portfolio');
  const [loading, setLoading] = useState(false);
  const [modalBorrowerId, setModalBorrowerId] = useState<string | null>(null);

  useEffect(() => {
    rmApi.getList().then(r => {
      setRmList(r.data);
      if (r.data.length > 0) setSelectedRm(r.data[0].rm_id);
    });
    rmApi.getComparison().then(r => setComparison(r.data));
  }, []);

  useEffect(() => {
    if (!selectedRm) return;
    setLoading(true);
    Promise.all([
      rmApi.getSummary(selectedRm),
      rmApi.getPortfolio(selectedRm),
      ewsActionApi.getList({ rm_id: selectedRm, limit: 100 }),
    ]).then(([s, p, a]) => {
      setSummary(s.data);
      setPortfolio(p.data);
      setActions(a.data);
      setLoading(false);
    });
  }, [selectedRm]);

  const pieData = summary ? [
    { name: 'A등급', value: summary.grade_a },
    { name: 'B등급', value: summary.grade_b },
    { name: 'C등급', value: summary.grade_c },
    { name: 'D등급', value: summary.grade_d },
  ].filter(d => d.value > 0) : [];

  const currentRm = rmList.find(r => r.rm_id === selectedRm);

  return (
    <div>
      {/* 기업 미니 모달 */}
      {modalBorrowerId && (
        <CompanyMiniModal
          borrowerId={modalBorrowerId}
          onClose={() => setModalBorrowerId(null)}
        />
      )}

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">RM 포트폴리오</h1>
        <select value={selectedRm} onChange={e => setSelectedRm(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm min-w-40">
          {rmList.map(r => (
            <option key={r.rm_id} value={r.rm_id}>{r.rm_name} ({r.branch})</option>
          ))}
        </select>
      </div>

      {/* RM 요약 카드 */}
      {summary && !loading && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
          <div className="flex items-start gap-6">
            <div>
              <div className="w-14 h-14 bg-blue-600 rounded-full flex items-center justify-center text-white text-xl font-bold mb-2">
                {summary.rm_name?.[0]}
              </div>
              <p className="text-base font-semibold text-gray-900">{summary.rm_name}</p>
              <p className="text-sm text-gray-500">{summary.branch} / {summary.team}</p>
            </div>
            <div className="flex-1 grid grid-cols-4 gap-4">
              {[
                { label: '관리 기업', value: summary.total_companies, icon: <Users size={16} className="text-blue-500" /> },
                { label: '총 여신', value: `${summary.total_exposure_억.toFixed(1)}억`, icon: <BarChart2 size={16} className="text-purple-500" /> },
                { label: '미완료 액션', value: summary.open_actions, icon: <AlertTriangle size={16} className="text-yellow-500" /> },
                { label: 'ECL 충당금', value: `${summary.ecl_amount_억.toFixed(1)}억`, icon: <TrendingDown size={16} className="text-red-500" /> },
              ].map(s => (
                <div key={s.label} className="bg-gray-50 rounded-xl p-3 flex items-center gap-2">
                  {s.icon}
                  <div>
                    <p className="text-xs text-gray-500">{s.label}</p>
                    <p className="text-lg font-bold text-gray-900">{s.value}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="w-36 h-36">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={30} outerRadius={55}>
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={GRADE_COLORS_PIE[entry.name[0]]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* 탭 */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-xl w-fit">
        {[
          { key: 'portfolio' as const, label: '담당 기업 목록' },
          { key: 'actions' as const, label: '액션 현황' },
          { key: 'compare' as const, label: 'RM 비교' },
        ].map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === t.key ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* 담당 기업 목록 */}
      {activeTab === 'portfolio' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['기업명','규모','업종','EWS등급','EWS점수','여신잔액(억)'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? (
                  <tr><td colSpan={6} className="text-center py-10 text-gray-400">로딩 중...</td></tr>
                ) : portfolio.map(c => (
                  <tr key={c.borrower_id}
                    className="hover:bg-blue-50 transition-colors cursor-pointer"
                    onClick={() => setModalBorrowerId(c.borrower_id)}
                  >
                    <td className="px-4 py-3 font-medium text-blue-700 hover:underline">{c.company_name}</td>
                    <td className="px-4 py-3 text-gray-600">{c.firm_size_cd}</td>
                    <td className="px-4 py-3 text-gray-600">{c.industry_cd}</td>
                    <td className="px-4 py-3">
                      {c.ews_grade ? (
                        <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${GRADE_BADGE[c.ews_grade] ?? ''}`}>
                          {c.ews_grade}
                        </span>
                      ) : '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{c.ews_score ?? '-'}</td>
                    <td className="px-4 py-3 text-gray-900">{c.total_outstanding_억.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 액션 현황 */}
      {activeTab === 'actions' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['기업명','경보월','등급','액션유형','상태','기한'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? (
                  <tr><td colSpan={6} className="text-center py-10 text-gray-400">로딩 중...</td></tr>
                ) : actions.map(a => (
                  <tr key={a.action_id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900">{a.company_name}</td>
                    <td className="px-4 py-3 text-gray-600">{a.ym}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${GRADE_BADGE[a.ews_grade] ?? ''}`}>
                        {a.ews_grade}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{a.action_type}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${STATUS_BADGE[a.status] ?? ''}`}>
                        {STATUS_LABEL[a.status] ?? a.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{a.due_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* RM 비교 */}
      {activeTab === 'compare' && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">RM 성과 비교</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={comparison.map(r => ({
                name: r.rm_name,
                total: r.total_companies,
                alert: r.alert_companies,
                completion: r.action_completion_pct,
              }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="total" name="관리기업수" fill="#3b82f6" radius={[4,4,0,0]} />
                <Bar dataKey="alert" name="위험기업수" fill="#ef4444" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  {['RM','지점','팀','관리기업','위험기업','위험비율','액션완료율'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {comparison.map(r => (
                  <tr key={r.rm_id} className={`hover:bg-gray-50 ${r.rm_id === selectedRm ? 'bg-blue-50' : ''}`}>
                    <td className="px-4 py-3 font-medium text-gray-900">{r.rm_name}</td>
                    <td className="px-4 py-3 text-gray-600">{r.branch}</td>
                    <td className="px-4 py-3 text-gray-600">{r.team}</td>
                    <td className="px-4 py-3 text-gray-900">{r.total_companies}</td>
                    <td className="px-4 py-3 text-red-600 font-medium">{r.alert_companies}</td>
                    <td className="px-4 py-3 text-gray-700">{r.risk_ratio_pct}%</td>
                    <td className="px-4 py-3 text-green-600 font-medium">{r.action_completion_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// BarChart2 아이콘 임시 정의 (lucide-react에서 import)
function BarChart2({ size, className }: { size: number; className: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" /><line x1="2" y1="20" x2="22" y2="20" />
    </svg>
  );
}

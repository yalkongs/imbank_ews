import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { monthlyReportApi } from '../utils/api';
import { formatEok } from '../utils/format';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts';

const MONTHS_36 = Array.from({ length: 35 }, (_, i) => {
  const base = 202302;
  const y = Math.floor(base / 100) + Math.floor(((base % 100) - 1 + i) / 12);
  const m = ((base % 100) - 1 + i) % 12 + 1;
  return y * 100 + m;
});

const GRADE_COLORS: Record<string, string> = {
  A: 'bg-green-100 text-green-700',
  B: 'bg-yellow-100 text-yellow-700',
  C: 'bg-orange-100 text-orange-700',
  D: 'bg-red-100 text-red-700',
};

export default function MonthlyReport() {
  const [ym, setYm] = useState(202512);
  const [summary, setSummary] = useState<any>(null);
  const [gradeChange, setGradeChange] = useState<any>(null);
  const [trend, setTrend] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      monthlyReportApi.getSummary(ym),
      monthlyReportApi.getGradeChange(ym),
      monthlyReportApi.getTrend(),
    ]).then(([s, g, t]) => {
      setSummary(s.data);
      setGradeChange(g.data);
      setTrend(t.data);
      setLoading(false);
    });
  }, [ym]);

  const trendData = trend.map(d => ({
    ym: String(d.ym),
    A: d.grade_a_cnt,
    B: d.grade_b_cnt,
    C: d.grade_c_cnt,
    D: d.grade_d_cnt,
  }));

  return (
    <div>
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">월간 EWS 보고서</h1>
        <select
          value={ym}
          onChange={e => setYm(Number(e.target.value))}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
        >
          {MONTHS_36.map(m => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400">로딩 중...</div>
      ) : (
        <>
          {/* 섹션 1: 이달의 EWS 현황 */}
          {summary && (
            <>
              <h2 className="text-base font-semibold text-gray-700 mb-3">이달의 EWS 현황</h2>
              <div className="grid grid-cols-6 gap-3 mb-6">
                {[
                  { label: '전체 기업', value: (summary.total_companies ?? 0).toLocaleString(), color: 'text-gray-900' },
                  { label: 'A등급', value: (summary.grade_a_cnt ?? 0).toLocaleString(), color: 'text-green-600' },
                  { label: 'B등급', value: (summary.grade_b_cnt ?? 0).toLocaleString(), color: 'text-yellow-500' },
                  { label: 'C등급', value: (summary.grade_c_cnt ?? 0).toLocaleString(), color: 'text-orange-500' },
                  { label: 'D등급', value: (summary.grade_d_cnt ?? 0).toLocaleString(), color: 'text-red-600' },
                  { label: '경보 노출액', value: formatEok(summary.alert_exposure_억 ?? 0), color: 'text-red-600' },
                ].map(s => (
                  <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4 text-center">
                    <p className="text-xs text-gray-500 mb-1">{s.label}</p>
                    <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* 섹션 2: 전월 대비 변동 */}
          {gradeChange && (
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-white border border-gray-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp size={16} className="text-green-500" />
                  <h3 className="text-sm font-semibold text-gray-700">
                    등급 상향 ({gradeChange.upgraded?.length ?? 0}개)
                  </h3>
                </div>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {(gradeChange.upgraded ?? []).slice(0, 15).map((c: any) => (
                    <div key={c.borrower_id} className="flex items-center justify-between text-sm">
                      <span className="text-gray-800 truncate">{c.company_name}</span>
                      <span className="flex items-center gap-1 ml-2 shrink-0">
                        <span className={`px-1.5 py-0.5 text-xs rounded ${GRADE_COLORS[c.prev_grade] ?? ''}`}>{c.prev_grade}</span>
                        <span className="text-gray-400">→</span>
                        <span className={`px-1.5 py-0.5 text-xs rounded ${GRADE_COLORS[c.cur_grade] ?? ''}`}>{c.cur_grade}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-white border border-gray-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingDown size={16} className="text-red-500" />
                  <h3 className="text-sm font-semibold text-gray-700">
                    등급 하향 ({gradeChange.downgraded?.length ?? 0}개)
                  </h3>
                </div>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {(gradeChange.downgraded ?? []).slice(0, 15).map((c: any) => (
                    <div key={c.borrower_id} className="flex items-center justify-between text-sm">
                      <span className="text-gray-800 truncate">{c.company_name}</span>
                      <span className="flex items-center gap-1 ml-2 shrink-0">
                        <span className={`px-1.5 py-0.5 text-xs rounded ${GRADE_COLORS[c.prev_grade] ?? ''}`}>{c.prev_grade}</span>
                        <span className="text-gray-400">→</span>
                        <span className={`px-1.5 py-0.5 text-xs rounded ${GRADE_COLORS[c.cur_grade] ?? ''}`}>{c.cur_grade}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* 신규/해소 배너 */}
          {summary && (
            <div className="grid grid-cols-4 gap-3 mb-6">
              {[
                { label: '등급 상향', value: summary.upgraded_cnt, color: 'bg-green-50 text-green-700', icon: <TrendingUp size={16} /> },
                { label: '등급 하향', value: summary.downgraded_cnt, color: 'bg-red-50 text-red-700', icon: <TrendingDown size={16} /> },
                { label: '신규 경보 발생', value: summary.new_alert_cnt, color: 'bg-orange-50 text-orange-700', icon: <AlertTriangle size={16} /> },
                { label: '경보 해소', value: summary.resolved_alert_cnt, color: 'bg-green-50 text-green-700', icon: <CheckCircle2 size={16} /> },
              ].map(s => (
                <div key={s.label} className={`rounded-xl p-4 flex items-center gap-3 ${s.color}`}>
                  {s.icon}
                  <div>
                    <p className="text-xs opacity-70">{s.label}</p>
                    <p className="text-xl font-bold">{s.value}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 섹션 3: 등급 분포 추이 */}
          <div className="bg-white border border-gray-200 rounded-xl p-4 mb-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">등급 분포 추이</h3>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="ym" tick={{ fontSize: 10 }} tickLine={false} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="A" stackId="1" fill="#16a34a" stroke="#16a34a" fillOpacity={0.7} name="A등급" />
                <Area type="monotone" dataKey="B" stackId="1" fill="#eab308" stroke="#eab308" fillOpacity={0.7} name="B등급" />
                <Area type="monotone" dataKey="C" stackId="1" fill="#f97316" stroke="#f97316" fillOpacity={0.7} name="C등급" />
                <Area type="monotone" dataKey="D" stackId="1" fill="#dc2626" stroke="#dc2626" fillOpacity={0.7} name="D등급" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* 섹션 4: 액션 완료율 */}
          {summary && (
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">이달의 액션 완료율</h3>
              <div className="flex items-center gap-4">
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className="bg-green-500 h-4 rounded-full transition-all duration-500"
                    style={{ width: `${summary.action_completion_pct ?? 0}%` }}
                  />
                </div>
                <span className="text-lg font-bold text-green-600 whitespace-nowrap">
                  {summary.action_completion_pct ?? 0}%
                </span>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { maturityApi } from '../utils/api';
import { formatNumber } from '../utils/format';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

type BucketKey = 'within_30' | 'within_60' | 'within_90' | 'within_180';

const TABS: { key: BucketKey; label: string }[] = [
  { key: 'within_30',  label: '30일 이내' },
  { key: 'within_60',  label: '60일 이내' },
  { key: 'within_90',  label: '90일 이내' },
  { key: 'within_180', label: '180일 이내' },
];

const GRADE_ROW: Record<string, string> = {
  D: 'bg-red-50',
  C: 'bg-orange-50',
};

const GRADE_BADGE: Record<string, string> = {
  A: 'bg-green-100 text-green-700',
  B: 'bg-yellow-100 text-yellow-700',
  C: 'bg-orange-100 text-orange-700',
  D: 'bg-red-100 text-red-700',
};

export default function MaturityCalendar() {
  const [summary, setSummary] = useState<any>(null);
  const [calendar, setCalendar] = useState<any>(null);
  const [heatmap, setHeatmap] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<BucketKey>('within_30');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      maturityApi.getSummary(),
      maturityApi.getCalendar(),
      maturityApi.getHeatmap(),
    ]).then(([s, c, h]) => {
      setSummary(s.data);
      setCalendar(c.data);
      setHeatmap(h.data);
      setLoading(false);
    });
  }, []);

  const tableData: any[] = calendar?.[activeTab] ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">만기 도래 캘린더</h1>

      {/* StatCards */}
      {summary && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[
            { label: '30일 이내 만기', cnt: summary.within_30_cnt, amt: summary.within_30_amt },
            { label: '60일 이내 만기', cnt: summary.within_60_cnt, amt: summary.within_60_amt },
            { label: '90일 이내 만기', cnt: summary.within_90_cnt, amt: summary.within_90_amt },
          ].map(s => (
            <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-xs text-gray-500 mb-1">{s.label}</p>
              <p className="text-2xl font-bold text-gray-900">{(s.cnt ?? 0).toLocaleString()}건</p>
              <p className="text-sm text-gray-500 mt-1">{formatNumber(s.amt ?? 0, 1)}억원</p>
            </div>
          ))}
        </div>
      )}

      {/* 탭 */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-xl w-fit">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === t.key ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 테이블 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['기업명','EWS등급','여신유형','잔액(억)','만기월','담당RM'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr><td colSpan={6} className="text-center py-10 text-gray-400">로딩 중...</td></tr>
              ) : tableData.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-10 text-gray-400">해당 기간 만기 여신 없음</td></tr>
              ) : tableData.map((r: any, i: number) => (
                <tr key={i} className={`${GRADE_ROW[r.ews_grade] ?? ''} hover:bg-gray-50 transition-colors`}>
                  <td className="px-4 py-3 font-medium text-gray-900">{r.company_name}</td>
                  <td className="px-4 py-3">
                    {r.ews_grade ? (
                      <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${GRADE_BADGE[r.ews_grade] ?? 'bg-gray-100 text-gray-600'}`}>
                        {r.ews_grade}
                      </span>
                    ) : '-'}
                  </td>
                  <td className="px-4 py-3 text-gray-700">{r.facility_type}</td>
                  <td className="px-4 py-3 text-gray-900 font-medium">{formatNumber(r.outstanding_amount_억 ?? 0, 1)}</td>
                  <td className="px-4 py-3 text-gray-700">{r.maturity_ym}</td>
                  <td className="px-4 py-3 text-gray-600">{r.rm_name || r.rm_id || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 히트맵 차트 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">향후 12개월 만기 도래 금액</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={heatmap.map(d => ({ ym: String(d.ym), amount: d.amount_억, count: d.count }))}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="ym" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v: any) => `${Number(v).toFixed(1)}억`} />
            <Bar dataKey="amount" name="만기금액(억)" fill="#1e40af" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { migrationApi } from '../utils/api';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

const GRADES = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC', 'D'];

const MONTHS_RATING = [
  202303, 202306, 202309, 202312,
  202403, 202406, 202409, 202412,
  202503, 202506, 202509, 202512,
];

function cellColor(fromIdx: number, toIdx: number, pct: number) {
  if (fromIdx === toIdx) {
    // 대각선 (유지)
    const intensity = Math.min(Math.round(pct / 100 * 200), 200);
    return `rgba(59, 130, 246, ${pct / 100 * 0.7 + 0.1})`;
  } else if (toIdx > fromIdx) {
    // 하향 (빨간색, 진할수록 이동 많음)
    return `rgba(220, 38, 38, ${Math.min(pct / 30, 1) * 0.6 + 0.05})`;
  } else {
    // 상향 (초록색)
    return `rgba(22, 163, 74, ${Math.min(pct / 30, 1) * 0.6 + 0.05})`;
  }
}

export default function MigrationMatrix() {
  const [fromYm, setFromYm] = useState(202303);
  const [toYm, setToYm]     = useState(202312);
  const [matrix, setMatrix] = useState<any>(null);
  const [pctMatrix, setPctMatrix] = useState<any>(null);
  const [totals, setTotals] = useState<any>(null);
  const [trendGrade, setTrendGrade] = useState('BB');
  const [trendData, setTrendData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showPct, setShowPct] = useState(false);

  useEffect(() => {
    setLoading(true);
    migrationApi.getMatrix(fromYm, toYm).then(r => {
      setMatrix(r.data.matrix);
      setPctMatrix(r.data.pct_matrix);
      setTotals(r.data.totals);
      setLoading(false);
    });
  }, [fromYm, toYm]);

  useEffect(() => {
    migrationApi.getTrend(trendGrade).then(r => setTrendData(r.data));
  }, [trendGrade]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">등급 전이 행렬</h1>

      {/* 기간 선택 */}
      <div className="flex items-center gap-4 mb-6 bg-white border border-gray-200 rounded-xl p-4">
        <label className="text-sm text-gray-600 font-medium">기준 시점:</label>
        <select value={fromYm} onChange={e => setFromYm(Number(e.target.value))}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
          {MONTHS_RATING.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <span className="text-gray-400">→</span>
        <label className="text-sm text-gray-600 font-medium">비교 시점:</label>
        <select value={toYm} onChange={e => setToYm(Number(e.target.value))}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
          {MONTHS_RATING.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-sm text-gray-500">표시:</span>
          <button onClick={() => setShowPct(false)}
            className={`px-3 py-1 rounded-lg text-sm ${!showPct ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}>
            기업 수
          </button>
          <button onClick={() => setShowPct(true)}
            className={`px-3 py-1 rounded-lg text-sm ${showPct ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}>
            비율(%)
          </button>
        </div>
      </div>

      {/* 행렬 테이블 */}
      {loading ? (
        <div className="text-center py-20 text-gray-400">로딩 중...</div>
      ) : matrix && (
        <div className="bg-white border border-gray-200 rounded-xl p-4 mb-6 overflow-x-auto">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            등급 전이 행렬 ({fromYm} → {toYm})
          </h3>
          <div className="mb-2 text-xs text-gray-400">행: 기준 등급 / 열: 이후 등급</div>
          <table className="text-xs border-collapse">
            <thead>
              <tr>
                <th className="w-12 p-1 text-center text-gray-500 font-medium">FROM＼TO</th>
                {GRADES.map(g => (
                  <th key={g} className="w-14 p-1 text-center font-semibold text-gray-700">{g}</th>
                ))}
                <th className="w-14 p-1 text-center text-gray-400 font-medium">합계</th>
              </tr>
            </thead>
            <tbody>
              {GRADES.map((fg, fi) => (
                <tr key={fg}>
                  <td className="p-1 text-center font-semibold text-gray-700 bg-gray-50">{fg}</td>
                  {GRADES.map((tg, ti) => {
                    const cnt  = matrix?.[fg]?.[tg] ?? 0;
                    const pct  = pctMatrix?.[fg]?.[tg] ?? 0;
                    const val  = showPct ? `${pct}%` : cnt;
                    const bg   = cellColor(fi, ti, pct);
                    return (
                      <td key={tg}
                        className="p-1 text-center font-medium border border-gray-100"
                        style={{ backgroundColor: bg, color: fi === ti ? '#1e3a8a' : pct > 0 ? '#1f2937' : '#9ca3af' }}>
                        {cnt > 0 ? val : '—'}
                      </td>
                    );
                  })}
                  <td className="p-1 text-center text-gray-500 bg-gray-50">
                    {totals?.[fg] ?? 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 flex gap-4 text-xs text-gray-400">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-200 inline-block" /> 등급 유지</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-200 inline-block" /> 등급 하향</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-200 inline-block" /> 등급 상향</span>
          </div>
        </div>
      )}

      {/* 하향 추이 */}
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <div className="flex items-center gap-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-700">하향 이동 추이</h3>
          <select value={trendGrade} onChange={e => setTrendGrade(e.target.value)}
            className="border border-gray-300 rounded-lg px-2 py-1 text-sm">
            {GRADES.slice(0, 7).map(g => <option key={g} value={g}>{g}</option>)}
          </select>
          <span className="text-xs text-gray-400">등급에서 하향된 기업 수 추이</span>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={trendData.map(d => ({ ym: String(d.ym), cnt: d.downgraded }))}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="ym" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line type="monotone" dataKey="cnt" stroke="#dc2626" strokeWidth={2} name="하향 기업 수" dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

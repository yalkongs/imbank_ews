import React, { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { concentrationApi } from '../utils/api';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

interface ConcentrationItem {
  dimension_value: string;
  label: string;
  exposure_억: number;
  exposure_pct: number;
  limit_pct: number;
  warning_pct: number;
  status: string;
}

interface StatusData {
  total_exposure_억: number;
  by_industry: ConcentrationItem[];
  by_firm_size: ConcentrationItem[];
  breach_count: number;
  warning_count: number;
}

const STATUS_COLOR: Record<string, string> = {
  BREACH: 'bg-red-500',
  WARNING: 'bg-yellow-400',
  NORMAL: 'bg-green-500',
};

function ProgressBar({ item }: { item: ConcentrationItem }) {
  const pct = Math.min(item.exposure_pct / item.limit_pct * 100, 120);
  const barColor = item.status === 'BREACH' ? 'bg-red-500' : item.status === 'WARNING' ? 'bg-yellow-400' : 'bg-green-500';
  const warnPos = (item.warning_pct / item.limit_pct) * 100;

  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-gray-800">{item.label}</span>
        <span className="text-xs text-gray-500">
          {item.exposure_억.toFixed(1)}억 / {item.exposure_pct.toFixed(1)}% (한도: {item.limit_pct.toFixed(1)}%)
        </span>
      </div>
      <div className="relative w-full bg-gray-200 rounded-full h-4 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
        {/* 경고선 */}
        <div
          className="absolute top-0 h-full w-0.5 bg-yellow-500 opacity-70"
          style={{ left: `${Math.min(warnPos, 100)}%` }}
        />
      </div>
    </div>
  );
}

export default function ConcentrationLimit() {
  const [data, setData] = useState<StatusData | null>(null);
  const [activeTab, setActiveTab] = useState<'industry' | 'size'>('industry');
  const [trendData, setTrendData] = useState<any[]>([]);
  const [selectedItem, setSelectedItem] = useState<ConcentrationItem | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    concentrationApi.getStatus().then(r => {
      setData(r.data);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (selectedItem) {
      const dim = activeTab === 'industry' ? 'INDUSTRY' : 'FIRM_SIZE';
      concentrationApi.getTrend(dim, selectedItem.dimension_value).then(r => {
        setTrendData(r.data);
      });
    }
  }, [selectedItem, activeTab]);

  const items = activeTab === 'industry' ? (data?.by_industry ?? []) : (data?.by_firm_size ?? []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">집중도 한도 관리</h1>

      {/* 배너 */}
      {data && (
        <div className="flex gap-3 mb-6">
          {data.breach_count > 0 && (
            <div className="flex items-center gap-2 px-4 py-2 bg-red-50 border border-red-200 rounded-xl text-red-700">
              <XCircle size={16} />
              <span className="text-sm font-medium">한도 초과 {data.breach_count}건</span>
            </div>
          )}
          {data.warning_count > 0 && (
            <div className="flex items-center gap-2 px-4 py-2 bg-yellow-50 border border-yellow-200 rounded-xl text-yellow-700">
              <AlertTriangle size={16} />
              <span className="text-sm font-medium">경고 {data.warning_count}건</span>
            </div>
          )}
          {data.breach_count === 0 && data.warning_count === 0 && (
            <div className="flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-xl text-green-700">
              <CheckCircle2 size={16} />
              <span className="text-sm font-medium">모든 집중도 한도 정상</span>
            </div>
          )}
          <div className="ml-auto text-sm text-gray-500 flex items-center">
            총 여신: <span className="font-bold text-gray-900 ml-1">{data.total_exposure_억.toFixed(1)}억</span>
          </div>
        </div>
      )}

      {/* 탭 */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-xl w-fit">
        {[
          { key: 'industry' as const, label: '업종별' },
          { key: 'size' as const, label: '기업규모별' },
        ].map(t => (
          <button key={t.key} onClick={() => { setActiveTab(t.key); setSelectedItem(null); }}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === t.key ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400">로딩 중...</div>
      ) : (
        <div className="grid grid-cols-2 gap-6">
          {/* 게이지 목록 */}
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">
              {activeTab === 'industry' ? '업종별 집중도' : '기업규모별 집중도'}
            </h3>
            {items.map(item => (
              <div key={item.dimension_value}
                onClick={() => setSelectedItem(item)}
                className={`cursor-pointer p-2 rounded-lg transition-colors ${selectedItem?.dimension_value === item.dimension_value ? 'bg-blue-50' : 'hover:bg-gray-50'}`}>
                <ProgressBar item={item} />
              </div>
            ))}
          </div>

          {/* 추이 차트 */}
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">
              {selectedItem ? `${selectedItem.label} 월별 추이` : '항목을 선택하세요'}
            </h3>
            {selectedItem && trendData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={trendData.map(d => ({
                  ym: String(d.ym),
                  pct: d.exposure_pct,
                  limit: selectedItem.limit_pct,
                  warning: selectedItem.warning_pct,
                }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="ym" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 11 }} unit="%" />
                  <Tooltip formatter={(v: any) => `${Number(v).toFixed(1)}%`} />
                  <Line type="monotone" dataKey="pct" stroke="#1e40af" strokeWidth={2} name="실제" dot={false} />
                  <Line type="monotone" dataKey="limit" stroke="#ef4444" strokeDasharray="4 2" strokeWidth={1} name="한도" dot={false} />
                  <Line type="monotone" dataKey="warning" stroke="#f59e0b" strokeDasharray="4 2" strokeWidth={1} name="경고" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
                좌측에서 항목을 클릭하면 추이가 표시됩니다
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { CheckCircle2, Clock, AlertCircle, XCircle, MapPin } from 'lucide-react';
import { ewsActionApi, rmApi } from '../utils/api';
import { BarChart as RBarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';

interface ActionItem {
  action_id: string;
  borrower_id: string;
  company_name: string;
  ym: number;
  ews_grade: string;
  action_type: string;
  action_date: string;
  rm_id: string;
  rm_name: string;
  status: string;
  due_date: string;
  note: string;
}

interface Summary {
  total: number;
  open: number;
  in_progress: number;
  completed: number;
  waived: number;
  completion_pct: number;
  by_type: { action_type: string; count: number }[];
  by_grade: { grade: string; count: number }[];
}

const STATUS_STYLE: Record<string, string> = {
  OPEN:        'bg-gray-100 text-gray-700',
  IN_PROGRESS: 'bg-blue-100 text-blue-700',
  COMPLETED:   'bg-green-100 text-green-700',
  WAIVED:      'bg-yellow-100 text-yellow-700',
};

const STATUS_LABEL: Record<string, string> = {
  OPEN: '대기', IN_PROGRESS: '진행중', COMPLETED: '완료', WAIVED: '면제',
};

const ACTION_LABEL: Record<string, string> = {
  VISIT: '방문',
  CALL: '전화',
  DOCUMENT_REQUEST: '서류요청',
  MONITORING: '모니터링',
  LIMIT_REDUCTION: '한도축소',
  COLLATERAL_ADD: '담보추가',
};

const GRADE_COLORS: Record<string, string> = {
  A: 'bg-green-100 text-green-700',
  B: 'bg-yellow-100 text-yellow-700',
  C: 'bg-orange-100 text-orange-700',
  D: 'bg-red-100 text-red-700',
};

export default function EWSAction() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [list, setList] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterGrade, setFilterGrade] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterRm, setFilterRm] = useState('');
  const [filterRegion, setFilterRegion] = useState('');
  const [rmList, setRmList] = useState<{ rm_id: string; rm_name: string }[]>([]);
  const [selected, setSelected] = useState<ActionItem | null>(null);

  useEffect(() => {
    ewsActionApi.getSummary().then(r => setSummary(r.data));
    rmApi.getList().then(r => setRmList(r.data));
  }, []);

  useEffect(() => {
    setLoading(true);
    ewsActionApi.getList({
      grade: filterGrade || undefined,
      status: filterStatus || undefined,
      rm_id: filterRm || undefined,
      region: filterRegion || undefined,
      limit: 100,
    }).then(r => {
      setList(r.data);
      setLoading(false);
    });
  }, [filterGrade, filterStatus, filterRm, filterRegion]);

  const today = new Date().toISOString().slice(0, 10);
  const overdueCount = list.filter(
    a => a.status === 'OPEN' && a.due_date < today
  ).length;

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">경보 액션 관리</h1>

      {/* StatCards */}
      {summary && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            { label: '전체 액션', value: summary.total.toLocaleString(), icon: <AlertCircle size={20} className="text-blue-500" /> },
            { label: '진행 중', value: summary.in_progress.toLocaleString(), icon: <Clock size={20} className="text-yellow-500" /> },
            { label: '완료율', value: `${summary.completion_pct}%`, icon: <CheckCircle2 size={20} className="text-green-500" /> },
            { label: '기한 초과', value: overdueCount.toLocaleString(), icon: <XCircle size={20} className="text-red-500" /> },
          ].map(s => (
            <div key={s.label} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3">
              <div className="p-2 bg-gray-50 rounded-lg">{s.icon}</div>
              <div>
                <p className="text-xs text-gray-500">{s.label}</p>
                <p className="text-xl font-bold text-gray-900">{s.value}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 필터 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4 flex gap-3 flex-wrap">
        <select value={filterGrade} onChange={e => setFilterGrade(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
          <option value="">전체 등급</option>
          <option value="C">C등급</option>
          <option value="D">D등급</option>
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
          <option value="">전체 상태</option>
          <option value="OPEN">대기</option>
          <option value="IN_PROGRESS">진행중</option>
          <option value="COMPLETED">완료</option>
          <option value="WAIVED">면제</option>
        </select>
        <select value={filterRm} onChange={e => setFilterRm(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
          <option value="">전체 RM</option>
          {rmList.map(r => (
            <option key={r.rm_id} value={r.rm_id}>{r.rm_name}</option>
          ))}
        </select>
        <div className="flex items-center gap-0.5 border border-gray-200 rounded-lg px-1.5 py-0.5 bg-white">
          <MapPin size={13} className="text-gray-400 mr-0.5" />
          {[{v:'',l:'전체'},{v:'수도권',l:'수도권'},{v:'대구경북',l:'대구경북'},{v:'부산경남',l:'부산경남'}].map(r => (
            <button key={r.v} onClick={() => setFilterRegion(r.v)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${filterRegion === r.v ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}>
              {r.l}
            </button>
          ))}
        </div>
      </div>

      {/* 테이블 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['기업명','경보월','등급','액션유형','담당RM','상태','기한','메모'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr><td colSpan={8} className="text-center py-10 text-gray-400">로딩 중...</td></tr>
              ) : list.map(a => (
                <tr key={a.action_id} onClick={() => setSelected(a)}
                  className="hover:bg-gray-50 cursor-pointer transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">{a.company_name}</td>
                  <td className="px-4 py-3 text-gray-600">{a.ym}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${GRADE_COLORS[a.ews_grade] ?? ''}`}>
                      {a.ews_grade}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{ACTION_LABEL[a.action_type] ?? a.action_type}</td>
                  <td className="px-4 py-3 text-gray-600">{a.rm_name || a.rm_id}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${STATUS_STYLE[a.status] ?? ''}`}>
                      {STATUS_LABEL[a.status] ?? a.status}
                    </span>
                  </td>
                  <td className={`px-4 py-3 text-xs ${a.due_date < today && a.status === 'OPEN' ? 'text-red-600 font-semibold' : 'text-gray-500'}`}>
                    {a.due_date}
                  </td>
                  <td className="px-4 py-3 text-gray-500 max-w-xs truncate">{a.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 차트 */}
      {summary && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">액션유형별 분포</h3>
            <ResponsiveContainer width="100%" height={200}>
              <RBarChart data={summary.by_type.map(d => ({ name: ACTION_LABEL[d.action_type] ?? d.action_type, count: d.count }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" radius={[4,4,0,0]} />
              </RBarChart>
            </ResponsiveContainer>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">등급별 액션 분포</h3>
            <ResponsiveContainer width="100%" height={200}>
              <RBarChart data={summary.by_grade}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="grade" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#f59e0b" radius={[4,4,0,0]} />
              </RBarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 상세 모달 */}
      {selected && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
          onClick={() => setSelected(null)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl"
            onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-gray-900 mb-4">{selected.company_name} 액션 상세</h3>
            <dl className="space-y-2 text-sm">
              {[
                ['액션ID', selected.action_id],
                ['경보월', selected.ym],
                ['EWS등급', selected.ews_grade],
                ['액션유형', ACTION_LABEL[selected.action_type] ?? selected.action_type],
                ['담당RM', selected.rm_name || selected.rm_id],
                ['상태', STATUS_LABEL[selected.status] ?? selected.status],
                ['액션일자', selected.action_date],
                ['기한', selected.due_date],
                ['메모', selected.note],
              ].map(([k, v]) => (
                <div key={k as string} className="flex gap-2">
                  <dt className="w-20 text-gray-500 shrink-0">{k}</dt>
                  <dd className="text-gray-900 font-medium">{v}</dd>
                </div>
              ))}
            </dl>
            <button onClick={() => setSelected(null)}
              className="mt-4 w-full py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm">
              닫기
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

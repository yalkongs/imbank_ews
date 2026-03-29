import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Filter, MapPin } from 'lucide-react';
import { Card } from '../components';
import Table from '../components/Table';
import { ewsApi } from '../utils/api';
import { getEWSGradeBgClass, formatYm } from '../utils/format';

const GRADES = ['', 'A', 'B', 'C', 'D'];
const FIRM_SIZES = ['', 'LARGE', 'MEDIUM', 'SMALL'];
const INDUSTRIES = ['', 'K00', 'K01', 'K01B', 'K02', 'K03', 'K04', 'K05', 'K06', 'K07', 'K08', 'K09', 'K10', 'K11', 'K12', 'K13'];

export default function EWSAlerts() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [latestYm, setLatestYm] = useState<number | undefined>(undefined);
  const [filterGrade, setFilterGrade] = useState('');
  const [filterFirmSize, setFilterFirmSize] = useState('');
  const [filterIndustry, setFilterIndustry] = useState('');
  const [filterRegion, setFilterRegion] = useState('');

  useEffect(() => {
    loadAlerts();
  }, [filterGrade, filterFirmSize, filterIndustry, filterRegion]);

  const loadAlerts = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (filterGrade) params.grade = filterGrade;
      if (filterFirmSize) params.firm_size = filterFirmSize;
      if (filterIndustry) params.industry = filterIndustry;
      if (filterRegion) params.region = filterRegion;
      const res = await ewsApi.getAlerts(params);
      setAlerts(res.data || []);
      if (res.data && res.data.length > 0 && !latestYm) {
        // latestYm is not returned by this endpoint; show from filter only
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      key: 'company_name', header: '기업명', width: '160px',
      render: (v: string, row: any) => (
        <button
          onClick={() => navigate(`/companies?id=${row.borrower_id}`)}
          className="text-blue-600 hover:underline font-medium"
        >
          {v}
        </button>
      )
    },
    {
      key: 'ews_grade', header: 'EWS등급', width: '80px', align: 'center' as const,
      render: (v: string) => (
        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${getEWSGradeBgClass(v)}`}>{v}</span>
      )
    },
    {
      key: 'ews_score', header: 'EWS점수', width: '80px', align: 'right' as const,
      render: (v: number) => <span className="font-mono">{v}</span>
    },
    {
      key: 'tier_label', header: '데이터 Tier', width: '80px', align: 'center' as const,
      render: (v: string, row: any) => (
        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${row.tier_color || ''}`}>{v}</span>
      )
    },
    {
      key: 'data_completeness_pct', header: '완성도', width: '70px', align: 'right' as const,
      render: (v: number) => <span className="font-mono text-xs">{v}%</span>
    },
    { key: 'ifrs9_stage', header: 'IFRS9 Stage', width: '90px', align: 'center' as const },
    {
      key: 'principal_past_due_days', header: '연체일수', width: '80px', align: 'right' as const,
      render: (v: number) => (
        <span className={`font-mono ${v > 30 ? 'text-red-600 font-semibold' : ''}`}>{v}일</span>
      )
    },
    {
      key: 'seizure_flag', header: '압류', width: '60px', align: 'center' as const,
      render: (v: number) => v ? <span className="text-red-600 font-semibold">Y</span> : <span className="text-gray-400">N</span>
    },
    {
      key: 'lawsuit_count_12m', header: '소송(12M)', width: '80px', align: 'right' as const,
      render: (v: number) => (
        <span className={v > 0 ? 'text-orange-600 font-semibold' : 'text-gray-400'}>{v}</span>
      )
    },
    { key: 'firm_size_cd', header: '규모', width: '70px', align: 'center' as const },
    { key: 'industry_cd', header: '업종', width: '70px', align: 'center' as const },
    { key: 'region', header: '소재지', width: '80px', align: 'center' as const,
      render: (v: string) => v ? <span className="text-xs text-blue-600">{v}</span> : '-'
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">EWS 경보센터</h1>
        <p className="text-sm text-gray-500 mt-1">EWS 등급별 경보 기업 현황</p>
      </div>

      {/* 필터 */}
      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-gray-500" />
            <span className="text-sm font-medium text-gray-700">필터:</span>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">EWS 등급</label>
            <select
              value={filterGrade}
              onChange={(e) => setFilterGrade(e.target.value)}
              className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">전체</option>
              {GRADES.slice(1).map(g => <option key={g} value={g}>{g}등급</option>)}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">기업 규모</label>
            <select
              value={filterFirmSize}
              onChange={(e) => setFilterFirmSize(e.target.value)}
              className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">전체</option>
              <option value="LARGE">대기업</option>
              <option value="MEDIUM">중기업</option>
              <option value="SMALL">소기업</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">업종</label>
            <select
              value={filterIndustry}
              onChange={(e) => setFilterIndustry(e.target.value)}
              className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">전체</option>
              {INDUSTRIES.slice(1).map(i => <option key={i} value={i}>{i}</option>)}
            </select>
          </div>

          <div className="flex items-center gap-1 border border-gray-200 rounded-lg px-1.5 py-0.5 bg-white">
            <MapPin size={13} className="text-gray-400" />
            {[{v:'',l:'전체'},{v:'수도권',l:'수도권'},{v:'대구경북',l:'대구경북'},{v:'부산경남',l:'부산경남'}].map(r => (
              <button key={r.v} onClick={() => setFilterRegion(r.v)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${filterRegion === r.v ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}>
                {r.l}
              </button>
            ))}
          </div>

          <div className="ml-auto text-sm text-gray-500">
            총 <span className="font-semibold text-gray-900">{alerts.length}</span>개 기업
          </div>
        </div>
      </Card>

      {/* 테이블 */}
      <Card title="EWS 경보 기업 목록" noPadding>
        <Table
          columns={columns}
          data={alerts}
          loading={loading}
          emptyMessage="해당 조건의 경보 기업이 없습니다"
        />
      </Card>
    </div>
  );
}

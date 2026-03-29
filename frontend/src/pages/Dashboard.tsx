import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Building2, TrendingUp, Shield } from 'lucide-react';
import { Card, StatCard, GaugeCard, TrendChart, DonutChart, COLORS } from '../components';
import Table from '../components/Table';
import { dashboardApi } from '../utils/api';
import { formatEok, formatPercent, getEWSGradeBgClass, getEWSGradeColor, formatYm } from '../utils/format';

export default function Dashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [initializing, setInitializing] = useState(false);
  const [summary, setSummary] = useState<any>(null);
  const [gradeTrend, setGradeTrend] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [summaryRes, trendRes, alertsRes] = await Promise.all([
        dashboardApi.getSummary(),
        dashboardApi.getGradeTrend(),
        dashboardApi.getEWSAlerts(),
      ]);
      setSummary(summaryRes.data);
      setGradeTrend(trendRes.data || []);
      setAlerts(alertsRes.data || []);
      setInitializing(false);
    } catch (error: any) {
      if (error.response?.status === 503) {
        setInitializing(true);
        setTimeout(loadData, 5000);
      } else {
        console.error('Dashboard data load error:', error);
      }
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (initializing) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        <p className="text-gray-600 font-medium">데이터베이스 초기화 중입니다...</p>
        <p className="text-gray-400 text-sm">최초 실행 시 약 1~2분 소요됩니다. 자동으로 새로고침됩니다.</p>
      </div>
    );
  }

  const gradeCounts = summary?.ews_grade_counts || { A: 0, B: 0, C: 0, D: 0 };
  const totalCompanies = summary?.total_companies || 0;
  const alertCount = summary?.alert_count || 0;
  const alertRate = totalCompanies > 0 ? (alertCount / totalCompanies) * 100 : 0;

  const gradeDonutData = [
    { name: 'A등급 (정상)', value: gradeCounts.A, color: getEWSGradeColor('A') },
    { name: 'B등급 (주의)', value: gradeCounts.B, color: getEWSGradeColor('B') },
    { name: 'C등급 (경고)', value: gradeCounts.C, color: getEWSGradeColor('C') },
    { name: 'D등급 (위험)', value: gradeCounts.D, color: getEWSGradeColor('D') },
  ].filter(d => d.value > 0);

  const alertColumns = [
    { key: 'company_name', header: '기업명', width: '180px' },
    {
      key: 'ews_grade', header: 'EWS등급', width: '80px', align: 'center' as const,
      render: (v: string) => (
        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${getEWSGradeBgClass(v)}`}>{v}</span>
      )
    },
    {
      key: 'ews_score', header: 'EWS점수', width: '80px', align: 'right' as const,
      render: (v: number) => <span className="font-mono text-red-600">{v}</span>
    },
    { key: 'ifrs9_stage', header: 'Stage', width: '70px', align: 'center' as const },
    { key: 'firm_size_cd', header: '규모', width: '70px', align: 'center' as const },
    { key: 'industry_cd', header: '업종', width: '80px', align: 'center' as const },
  ];

  return (
    <div className="space-y-6">
      {/* 페이지 제목 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">EWS 대시보드</h1>
          <p className="text-sm text-gray-500 mt-1">
            기준월: {formatYm(summary?.latest_ym || '')} | 총 모니터링 기업 {totalCompanies.toLocaleString()}개
          </p>
        </div>
      </div>

      {/* StatCards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="총 모니터링 기업"
          value={totalCompanies.toLocaleString()}
          subtitle="전체 여신 보유 기업"
          icon={<Building2 size={20} />}
          color="blue"
        />
        <StatCard
          title="D등급 (위험)"
          value={gradeCounts.D}
          subtitle={`전체의 ${totalCompanies > 0 ? ((gradeCounts.D / totalCompanies) * 100).toFixed(1) : 0}%`}
          icon={<AlertTriangle size={20} />}
          color="red"
        />
        <StatCard
          title="C등급 (경고)"
          value={gradeCounts.C}
          subtitle={`전체의 ${totalCompanies > 0 ? ((gradeCounts.C / totalCompanies) * 100).toFixed(1) : 0}%`}
          icon={<AlertTriangle size={20} />}
          color="yellow"
        />
        <StatCard
          title="평균 ECL 비율"
          value={formatPercent(summary?.avg_ecl_rate || 0)}
          subtitle="최신 기준월 기준"
          icon={<TrendingUp size={20} />}
          color="gray"
        />
      </div>

      {/* 경보율 게이지 + 등급 분포 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GaugeCard
          title="EWS 경보율 (C+D등급 비율)"
          value={parseFloat(alertRate.toFixed(2))}
          max={100}
          min={0}
          unit="%"
          warning={15}
          critical={25}
        />

        <Card title="EWS 등급 분포" className="lg:col-span-2">
          <DonutChart
            data={gradeDonutData}
            height={220}
            centerText="EWS 등급"
            centerValue={totalCompanies.toString()}
          />
        </Card>
      </div>

      {/* 12개월 추이 */}
      <Card title="12개월 EWS 등급 추이">
        <TrendChart
          data={gradeTrend}
          xAxisKey="label"
          lines={[
            { key: 'A', name: 'A등급', color: getEWSGradeColor('A') },
            { key: 'B', name: 'B등급', color: getEWSGradeColor('B') },
            { key: 'C', name: 'C등급', color: getEWSGradeColor('C') },
            { key: 'D', name: 'D등급', color: getEWSGradeColor('D') },
          ]}
          height={280}
        />
      </Card>

      {/* 경보 기업 상위 10 */}
      <Card
        title="EWS 경보 기업 (C/D등급)"
        subtitle="EWS 점수 낮은 순"
        headerAction={
          <button
            onClick={() => navigate('/ews-alerts')}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            전체 보기 →
          </button>
        }
      >
        <Table
          columns={alertColumns}
          data={alerts.slice(0, 10)}
          onRowClick={(row) => navigate(`/companies?id=${row.borrower_id}`)}
        />
      </Card>
    </div>
  );
}

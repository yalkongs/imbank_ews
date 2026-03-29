import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Building2, TrendingUp, TrendingDown, Shield, DollarSign, ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { Card, StatCard, GaugeCard, TrendChart, DonutChart, GroupedBarChart, COLORS } from '../components';
import Table from '../components/Table';
import { dashboardApi } from '../utils/api';
import { formatEok, formatPercent, getEWSGradeBgClass, getEWSGradeColor, formatYm } from '../utils/format';

function DeltaBadge({ value, suffix = '', inverse = false }: { value: number; suffix?: string; inverse?: boolean }) {
  if (value === 0) return <span className="text-xs text-gray-400 flex items-center gap-0.5"><Minus size={12} />전월 동일</span>;
  const positive = inverse ? value < 0 : value > 0;
  return (
    <span className={`text-xs flex items-center gap-0.5 ${positive ? 'text-green-600' : 'text-red-500'}`}>
      {positive ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
      {Math.abs(value).toLocaleString()}{suffix} 전월 대비
    </span>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [initializing, setInitializing] = useState(false);
  const [summary, setSummary] = useState<any>(null);
  const [gradeTrend, setGradeTrend] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [industryBreakdown, setIndustryBreakdown] = useState<any[]>([]);
  const [regionBreakdown, setRegionBreakdown] = useState<any[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const results = await Promise.allSettled([
        dashboardApi.getSummary(),
        dashboardApi.getGradeTrend(),
        dashboardApi.getEWSAlerts(),
        dashboardApi.getIndustryBreakdown(),
        dashboardApi.getRegionBreakdown(),
      ]);

      const [summaryR, trendR, alertsR, industryR, regionR] = results;

      // 503이면 초기화 중 처리
      const is503 = results.some(
        r => r.status === 'rejected' && (r.reason as any)?.response?.status === 503
      );
      if (is503) {
        setInitializing(true);
        setTimeout(loadData, 5000);
        return;
      }

      if (summaryR.status === 'fulfilled') setSummary(summaryR.value.data);
      if (trendR.status === 'fulfilled') setGradeTrend(trendR.value.data || []);
      if (alertsR.status === 'fulfilled') setAlerts(alertsR.value.data || []);
      if (industryR.status === 'fulfilled') setIndustryBreakdown(industryR.value.data || []);
      if (regionR.status === 'fulfilled') setRegionBreakdown(regionR.value.data || []);

      setInitializing(false);
    } catch (error) {
      console.error('Dashboard data load error:', error);
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
  const prevGradeCounts = summary?.prev_grade_counts || { A: 0, B: 0, C: 0, D: 0 };
  const totalCompanies = summary?.total_companies || 0;
  const alertCount = summary?.alert_count || 0;
  const alertRate = totalCompanies > 0 ? (alertCount / totalCompanies) * 100 : 0;
  const gradeDownCount = summary?.grade_down_count || 0;
  const newAlertCount = summary?.new_alert_count || 0;
  const nplExposure = summary?.npl_exposure_억 || 0;
  const totalExposure = summary?.total_exposure_억 || 0;
  const avgEclRate = summary?.avg_ecl_rate || 0;
  const prevEclRate = summary?.prev_ecl_rate || 0;
  const eclDelta = parseFloat((avgEclRate - prevEclRate).toFixed(2));

  const gradeDonutData = [
    { name: 'A등급 (정상)', value: gradeCounts.A, color: getEWSGradeColor('A') },
    { name: 'B등급 (주의)', value: gradeCounts.B, color: getEWSGradeColor('B') },
    { name: 'C등급 (경고)', value: gradeCounts.C, color: getEWSGradeColor('C') },
    { name: 'D등급 (위험)', value: gradeCounts.D, color: getEWSGradeColor('D') },
  ].filter(d => d.value > 0);

  // 업종별 경보율 상위 8개
  const industryChartData = industryBreakdown.slice(0, 8).map(d => ({
    name: d.name,
    경보기업: d.alert_count,
    정상기업: d.total - d.alert_count,
  }));

  // 지역별 현황
  const regionChartData = regionBreakdown.map(d => ({
    name: d.region,
    'D등급': d.D,
    'C등급': d.C,
    'B등급': d.B,
    'A등급': d.A,
  }));

  const alertColumns = [
    { key: 'company_name', header: '기업명', width: '160px' },
    {
      key: 'ews_grade', header: 'EWS', width: '60px', align: 'center' as const,
      render: (v: string) => (
        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${getEWSGradeBgClass(v)}`}>{v}</span>
      )
    },
    {
      key: 'ews_score', header: '점수', width: '60px', align: 'right' as const,
      render: (v: number) => <span className="font-mono text-red-600 text-xs">{v}</span>
    },
    { key: 'ifrs9_stage', header: 'Stage', width: '55px', align: 'center' as const },
    { key: 'firm_size_cd', header: '규모', width: '55px', align: 'center' as const },
    { key: 'industry_cd', header: '업종', width: '65px', align: 'center' as const },
    { key: 'region', header: '지역', width: '80px', align: 'center' as const },
    {
      key: 'exposure_억', header: '여신(억)', width: '80px', align: 'right' as const,
      render: (v: number) => <span className="font-mono text-xs">{v.toLocaleString()}</span>
    },
  ];

  return (
    <div className="space-y-6">
      {/* 페이지 제목 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">EWS 대시보드</h1>
          <p className="text-sm text-gray-500 mt-1">
            기준월: <span className="font-semibold text-gray-700">{formatYm(summary?.latest_ym || '')}</span>
            &nbsp;|&nbsp; 전월: {formatYm(summary?.prev_ym || '')}
            &nbsp;|&nbsp; 총 모니터링 기업 <span className="font-semibold text-gray-700">{totalCompanies.toLocaleString()}</span>개
          </p>
        </div>
      </div>

      {/* StatCards Row 1: 핵심 지표 */}
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
          value={gradeCounts.D.toLocaleString()}
          subtitle={
            <span className="flex flex-col gap-0.5">
              <span>전체의 {totalCompanies > 0 ? ((gradeCounts.D / totalCompanies) * 100).toFixed(1) : 0}%</span>
              <DeltaBadge value={gradeCounts.D - prevGradeCounts.D} inverse={false} />
            </span>
          }
          icon={<AlertTriangle size={20} />}
          color="red"
        />
        <StatCard
          title="C등급 (경고)"
          value={gradeCounts.C.toLocaleString()}
          subtitle={
            <span className="flex flex-col gap-0.5">
              <span>전체의 {totalCompanies > 0 ? ((gradeCounts.C / totalCompanies) * 100).toFixed(1) : 0}%</span>
              <DeltaBadge value={gradeCounts.C - prevGradeCounts.C} inverse={false} />
            </span>
          }
          icon={<AlertTriangle size={20} />}
          color="yellow"
        />
        <StatCard
          title="평균 ECL 비율"
          value={formatPercent(avgEclRate)}
          subtitle={
            <span className="flex flex-col gap-0.5">
              <span>최신 기준월 기준</span>
              <DeltaBadge value={eclDelta} suffix="%" inverse={false} />
            </span>
          }
          icon={<TrendingUp size={20} />}
          color="gray"
        />
      </div>

      {/* StatCards Row 2: 변화 지표 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="신규 경보 기업"
          value={newAlertCount.toLocaleString()}
          subtitle="전월 정상→이번달 C/D"
          icon={<ArrowDownRight size={20} />}
          color="red"
        />
        <StatCard
          title="등급 하락 기업"
          value={gradeDownCount.toLocaleString()}
          subtitle="전월 A/B→이번달 C/D"
          icon={<TrendingDown size={20} />}
          color="orange"
        />
        <StatCard
          title="D등급 여신 잔액"
          value={`${nplExposure.toLocaleString()}억`}
          subtitle={`총 여신의 ${totalExposure > 0 ? ((nplExposure / totalExposure) * 100).toFixed(1) : 0}%`}
          icon={<DollarSign size={20} />}
          color="red"
        />
        <StatCard
          title="총 여신 잔액"
          value={`${totalExposure.toLocaleString()}억`}
          subtitle="전체 여신 포트폴리오"
          icon={<Shield size={20} />}
          color="blue"
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

      {/* 업종별 경보 현황 + 지역별 현황 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="업종별 경보 현황" subtitle="경보율 상위 8개 업종">
          <GroupedBarChart
            data={industryChartData}
            xAxisKey="name"
            bars={[
              { key: '경보기업', name: '경보(C/D)', color: '#ef4444' },
              { key: '정상기업', name: '정상(A/B)', color: '#93c5fd' },
            ]}
            height={260}
          />
        </Card>

        <Card title="지역별 EWS 현황">
          <div className="space-y-3 mt-2">
            {regionBreakdown.map(r => {
              const alertRateNum = r.alert_rate as number;
              return (
                <div key={r.region} className="flex items-center gap-3">
                  <div className="w-20 text-sm font-medium text-gray-700 shrink-0">{r.region}</div>
                  <div className="flex-1">
                    <div className="flex gap-0.5 h-5 rounded overflow-hidden">
                      {(['A', 'B', 'C', 'D'] as const).map(g => {
                        const pct = r.total > 0 ? (r[g] / r.total) * 100 : 0;
                        return pct > 0 ? (
                          <div
                            key={g}
                            title={`${g}등급: ${r[g]}개 (${pct.toFixed(1)}%)`}
                            style={{ width: `${pct}%`, backgroundColor: getEWSGradeColor(g) }}
                          />
                        ) : null;
                      })}
                    </div>
                  </div>
                  <div className="w-28 text-right text-xs text-gray-500 shrink-0">
                    <span className="text-red-500 font-semibold">{alertRateNum.toFixed(1)}%</span>
                    &nbsp;경보&nbsp;|&nbsp;{r.total.toLocaleString()}개
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex gap-4 mt-4 pt-3 border-t">
            {['A', 'B', 'C', 'D'].map(g => (
              <div key={g} className="flex items-center gap-1.5 text-xs text-gray-500">
                <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: getEWSGradeColor(g) }} />
                {g}등급
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* 경보 기업 상위 목록 */}
      <Card
        title="EWS 경보 기업 (C/D등급)"
        subtitle="EWS 점수 낮은 순 · 상위 10개"
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

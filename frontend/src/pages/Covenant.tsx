import React, { useEffect, useState } from 'react';
import { Card, StatCard, GroupedBarChart, TrendChart, COLORS } from '../components';
import Table from '../components/Table';
import { covenantApi } from '../utils/api';
import { formatPercent, formatYm, getStatusColorClass } from '../utils/format';
import { Shield } from 'lucide-react';

export default function Covenant() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<any>(null);
  const [breaches, setBreaches] = useState<any[]>([]);
  const [trend, setTrend] = useState<any[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [summaryRes, breachRes, trendRes] = await Promise.all([
        covenantApi.getSummary(),
        covenantApi.getBreaches(),
        covenantApi.getTrend(),
      ]);
      setSummary(summaryRes.data);
      setBreaches(breachRes.data || []);
      setTrend(trendRes.data || []);
    } catch (err) {
      console.error(err);
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

  const byTypeBarData = (summary?.by_type || []).map((d: any) => ({
    name: d.covenant_type,
    위반: d.breach,
    통과: d.pass,
    면제: d.waived,
  }));

  const breachColumns = [
    { key: 'company_name', header: '기업명', width: '150px' },
    { key: 'check_ym', header: '점검월', width: '80px', render: (v: number) => formatYm(v) },
    { key: 'covenant_type', header: '코베넌트 유형', width: '110px' },
    {
      key: 'result', header: '결과', width: '70px', align: 'center' as const,
      render: (v: string) => (
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColorClass(v)}`}>{v}</span>
      )
    },
    {
      key: 'actual_value', header: '실제값', width: '80px', align: 'right' as const,
      render: (v: number) => <span className="font-mono text-red-600">{v?.toFixed(3)}</span>
    },
    {
      key: 'threshold_value', header: '기준값', width: '80px', align: 'right' as const,
      render: (v: number) => <span className="font-mono">{v?.toFixed(3)}</span>
    },
    { key: 'firm_size_cd', header: '규모', width: '70px', align: 'center' as const },
    { key: 'industry_cd', header: '업종', width: '70px', align: 'center' as const },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">코베넌트 모니터링</h1>
        <p className="text-sm text-gray-500 mt-1">여신 약정 조건 위반 현황 관리</p>
      </div>

      {/* StatCards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="총 점검 건수"
          value={summary?.total_checks?.toLocaleString() || 0}
          icon={<Shield size={20} />}
          color="blue"
        />
        <StatCard
          title="위반 건수"
          value={summary?.breach_count?.toLocaleString() || 0}
          subtitle={`위반율 ${formatPercent(summary?.breach_rate_pct || 0)}`}
          color="red"
        />
        <StatCard
          title="면제 건수"
          value={summary?.waived_count?.toLocaleString() || 0}
          color="yellow"
        />
      </div>

      {/* 유형별 코베넌트 현황 */}
      <Card title="코베넌트 유형별 현황">
        <GroupedBarChart
          data={byTypeBarData}
          xAxisKey="name"
          bars={[
            { key: '위반', name: '위반', color: COLORS.danger },
            { key: '통과', name: '통과', color: COLORS.success },
            { key: '면제', name: '면제', color: COLORS.warning },
          ]}
          height={280}
        />
      </Card>

      {/* 월별 위반율 추이 */}
      <Card title="월별 코베넌트 위반율 추이 (%)">
        <TrendChart
          data={trend}
          xAxisKey="label"
          lines={[
            { key: 'breach_rate_pct', name: '위반율(%)', color: COLORS.danger },
          ]}
          height={250}
          showLegend={false}
          referenceLines={[{ y: 10, label: '10%', color: COLORS.warning }]}
        />
      </Card>

      {/* 위반 목록 */}
      <Card title="코베넌트 위반 목록" subtitle="최근 위반 건 순" noPadding>
        <Table
          columns={breachColumns}
          data={breaches}
          emptyMessage="코베넌트 위반 건이 없습니다"
        />
      </Card>
    </div>
  );
}

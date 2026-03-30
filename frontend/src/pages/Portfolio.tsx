import React, { useEffect, useState } from 'react';
import { Card, StatCard, DonutChart, GroupedBarChart, COLORS } from '../components';
import { portfolioApi } from '../utils/api';
import { formatEok, formatNumber } from '../utils/format';
import { PieChart, TrendingUp } from 'lucide-react';

export default function Portfolio() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<any>(null);
  const [concentration, setConcentration] = useState<any>(null);
  const [eclSummary, setEclSummary] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [summaryRes, concRes, eclRes] = await Promise.all([
        portfolioApi.getSummary(),
        portfolioApi.getConcentration(),
        portfolioApi.getECLSummary(),
      ]);
      setSummary(summaryRes.data);
      setConcentration(concRes.data);
      setEclSummary(eclRes.data);
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

  const industryBarData = (summary?.by_industry || []).map((d: any) => ({
    name: d.industry_cd,
    outstanding: d.outstanding_억,
  }));

  const sizeBarData = (summary?.by_firm_size || []).map((d: any) => ({
    name: d.firm_size_cd,
    outstanding: d.outstanding_억,
  }));

  const facilityTypeDonut = (summary?.by_facility_type || []).map((d: any, i: number) => ({
    name: d.facility_type,
    value: d.outstanding_억,
    color: COLORS.palette[i % COLORS.palette.length],
  }));

  const eclStageDonut = (eclSummary?.by_stage || []).map((d: any, i: number) => ({
    name: `Stage ${d.stage}`,
    value: d.ecl_억,
    color: ['#10b981', '#f59e0b', '#ef4444'][i] || COLORS.palette[i],
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">포트폴리오 분석</h1>
        <p className="text-sm text-gray-500 mt-1">업종·규모별 여신 집중도 및 ECL 현황</p>
      </div>

      {/* StatCards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="총 여신 잔액"
          value={formatEok(summary?.total_outstanding_억 || 0)}
          subtitle={`약정 ${formatEok(summary?.total_committed_억 || 0)}`}
          icon={<TrendingUp size={20} />}
          color="blue"
        />
        <StatCard
          title="총 ECL"
          value={formatEok(eclSummary?.total_ecl_억 || 0, 2)}
          subtitle={`EAD ${formatEok(eclSummary?.total_ead_억 || 0)}`}
          icon={<PieChart size={20} />}
          color="red"
        />
        <StatCard
          title="업종 집중도 (HHI)"
          value={(concentration?.hhi || 0).toFixed(1)}
          subtitle="1000 이상 시 집중 위험"
          color="yellow"
        />
      </div>

      {/* 업종별 여신 + 규모별 여신 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="업종별 여신 잔액 (억)">
          <GroupedBarChart
            data={industryBarData}
            xAxisKey="name"
            bars={[{ key: 'outstanding', name: '잔액(억)', color: COLORS.primary }]}
            height={300}
            showLegend={false}
          />
        </Card>
        <Card title="기업 규모별 여신 잔액 (억)">
          <GroupedBarChart
            data={sizeBarData}
            xAxisKey="name"
            bars={[{ key: 'outstanding', name: '잔액(억)', color: COLORS.accent }]}
            height={300}
            showLegend={false}
          />
        </Card>
      </div>

      {/* 여신유형 도넛 + ECL Stage 도넛 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="여신 유형별 분포">
          <DonutChart
            data={facilityTypeDonut}
            height={250}
            centerText="여신유형"
          />
        </Card>
        <Card title="ECL Stage별 분포 (억)">
          <DonutChart
            data={eclStageDonut}
            height={250}
            centerText="ECL 합계"
            centerValue={formatEok(eclSummary?.total_ecl_억 || 0, 1)}
          />
        </Card>
      </div>

      {/* 업종 집중도 테이블 */}
      <Card title="업종별 집중도 상세">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-left">업종코드</th>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-right">잔액(억)</th>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-right">비중(%)</th>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-left">비중 게이지</th>
              </tr>
            </thead>
            <tbody>
              {(concentration?.items || []).map((item: any, i: number) => (
                <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{item.industry_cd}</td>
                  <td className="px-4 py-3 font-mono text-right">{formatNumber(item.amount_억, 1)}</td>
                  <td className="px-4 py-3 font-mono text-right">{item.share_pct.toFixed(1)}%</td>
                  <td className="px-4 py-3">
                    <div className="h-2 bg-gray-200 rounded-full overflow-hidden w-full">
                      <div
                        className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${Math.min(item.share_pct, 100)}%` }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { Card, StatCard, TrendChart, GroupedBarChart, COLORS } from '../components';
import { eclApi } from '../utils/api';
import { formatEok, formatPercent, formatYm } from '../utils/format';
import { FileText } from 'lucide-react';

export default function ECLManagement() {
  const [loading, setLoading] = useState(true);
  const [ecl, setEcl] = useState<any>(null);
  const [trend, setTrend] = useState<any[]>([]);
  const [byGrade, setByGrade] = useState<any[]>([]);
  const [stageTrend, setStageTrend] = useState<any[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [eclRes, trendRes, gradeRes, stageTrendRes] = await Promise.all([
        eclApi.getSummary(),
        eclApi.getTrend(),
        eclApi.getByGrade(),
        eclApi.getByStageTrend(),
      ]);
      setEcl(eclRes.data);
      setTrend(trendRes.data || []);
      setByGrade(gradeRes.data || []);
      setStageTrend(stageTrendRes.data || []);
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

  const byStage = ecl?.by_stage || [];
  const stage1 = byStage.find((s: any) => s.stage === 1) || {};
  const stage2 = byStage.find((s: any) => s.stage === 2) || {};
  const stage3 = byStage.find((s: any) => s.stage === 3) || {};

  const gradeBarData = byGrade.map((d: any) => ({
    name: `${d.ews_grade}등급`,
    ecl: d.ecl_억,
    ead: d.ead_억,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">IFRS9 ECL 관리</h1>
        <p className="text-sm text-gray-500 mt-1">기준월: {formatYm(ecl?.latest_ym || '')}</p>
      </div>

      {/* StatCards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="총 ECL"
          value={formatEok(ecl?.total_ecl_억 || 0, 2)}
          subtitle={`ECL율 ${formatPercent(ecl?.ecl_rate_pct || 0, 3)}`}
          icon={<FileText size={20} />}
          color="red"
        />
        <StatCard
          title="Stage 1 ECL"
          value={formatEok(stage1.ecl_억 || 0, 2)}
          subtitle={`${stage1.count || 0}건`}
          color="green"
        />
        <StatCard
          title="Stage 2 ECL"
          value={formatEok(stage2.ecl_억 || 0, 2)}
          subtitle={`${stage2.count || 0}건`}
          color="yellow"
        />
        <StatCard
          title="Stage 3 ECL"
          value={formatEok(stage3.ecl_억 || 0, 2)}
          subtitle={`${stage3.count || 0}건`}
          color="red"
        />
      </div>

      {/* Stage별 평균 PD/LGD */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {byStage.map((s: any) => {
          const stageLabel = s.stage === 1 ? '정상 (Stage 1)' : s.stage === 2 ? '요주의 (Stage 2)' : '고정이하 (Stage 3)';
          const stageColor = s.stage === 1 ? 'text-green-700' : s.stage === 2 ? 'text-yellow-700' : 'text-red-700';
          return (
            <Card key={s.stage} title={stageLabel}>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">평균 PD</span>
                  <span className={`font-mono font-semibold ${stageColor}`}>{formatPercent(s.avg_pd * 100, 2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">평균 LGD</span>
                  <span className={`font-mono font-semibold ${stageColor}`}>{formatPercent(s.avg_lgd * 100, 1)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">총 EAD</span>
                  <span className="font-mono">{formatEok(s.ead_억, 1)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">총 ECL</span>
                  <span className="font-mono text-red-600">{formatEok(s.ecl_억, 3)}</span>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* ECL 추이 */}
      <Card title="월별 ECL 추이 (억)">
        <TrendChart
          data={trend}
          xAxisKey="label"
          lines={[
            { key: 'ecl_억', name: 'ECL(억)', color: COLORS.danger },
          ]}
          height={280}
        />
      </Card>

      {/* Stage별 ECL 스택 추이 */}
      <Card title="Stage별 ECL 분류 추이 (억)">
        <TrendChart
          data={stageTrend}
          xAxisKey="label"
          lines={[
            { key: 'stage1_ecl', name: '정상 (Stage 1)', color: COLORS.success },
            { key: 'stage2_ecl', name: '요주의 (Stage 2)', color: COLORS.warning },
            { key: 'stage3_ecl', name: '고정이하 (Stage 3)', color: COLORS.danger },
          ]}
          height={280}
        />
      </Card>

      {/* EWS 등급별 ECL */}
      <Card title="EWS 등급별 ECL 분포 (억)">
        <GroupedBarChart
          data={gradeBarData}
          xAxisKey="name"
          bars={[
            { key: 'ecl', name: 'ECL(억)', color: COLORS.danger },
            { key: 'ead', name: 'EAD(억)', color: COLORS.gray },
          ]}
          height={280}
        />
      </Card>
    </div>
  );
}

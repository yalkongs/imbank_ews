import React, { useEffect, useState } from 'react';
import { Card, DonutChart, StackedAreaChart } from '../components';
import Table from '../components/Table';
import { assetClassificationApi } from '../utils/api';
import { getClassificationLabel, getClassificationColor, formatYm } from '../utils/format';

const CLASSIFICATIONS = ['NORMAL', 'PRECAUTIONARY', 'SUBSTANDARD', 'DOUBTFUL', 'LOSS'];

export default function AssetClassification() {
  const [loading, setLoading] = useState(true);
  const [distribution, setDistribution] = useState<any>(null);
  const [trend, setTrend] = useState<any[]>([]);
  const [list, setList] = useState<any[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [distRes, trendRes, listRes] = await Promise.all([
        assetClassificationApi.getDistribution(),
        assetClassificationApi.getTrend(),
        assetClassificationApi.getList(),
      ]);
      setDistribution(distRes.data);
      setTrend(trendRes.data || []);
      setList(listRes.data || []);
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

  const donutData = (distribution?.distribution || []).filter((d: any) => d.count > 0).map((d: any) => ({
    name: getClassificationLabel(d.classification),
    value: d.count,
    color: getClassificationColor(d.classification),
  }));

  const totalCount = (distribution?.distribution || []).reduce((s: number, d: any) => s + d.count, 0);

  const columns = [
    { key: 'company_name', header: '기업명', width: '160px' },
    {
      key: 'classification', header: '건전성 분류', width: '120px',
      render: (v: string) => (
        <span className="px-2 py-0.5 rounded text-xs font-medium" style={{
          backgroundColor: getClassificationColor(v) + '20',
          color: getClassificationColor(v)
        }}>
          {getClassificationLabel(v)}
        </span>
      )
    },
    {
      key: 'ews_score', header: 'EWS점수', width: '80px', align: 'right' as const,
      render: (v: number) => <span className="font-mono">{v?.toFixed(1)}</span>
    },
    { key: 'firm_size_cd', header: '규모', width: '70px', align: 'center' as const },
    { key: 'industry_cd', header: '업종', width: '70px', align: 'center' as const },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">자산건전성 분류</h1>
        <p className="text-sm text-gray-500 mt-1">
          기준월: {formatYm(distribution?.ym || '')} | 총 {totalCount}건
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 분포 도넛 */}
        <Card title="자산건전성 분류 분포">
          <DonutChart
            data={donutData}
            height={260}
            centerText="총 기업"
            centerValue={totalCount.toString()}
          />
        </Card>

        {/* 분류별 통계 */}
        <Card title="분류별 현황">
          <div className="space-y-3">
            {(distribution?.distribution || []).map((d: any) => (
              <div key={d.classification} className="flex items-center gap-3">
                <div className="w-24 text-sm font-medium" style={{ color: getClassificationColor(d.classification) }}>
                  {getClassificationLabel(d.classification)}
                </div>
                <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: totalCount > 0 ? `${(d.count / totalCount) * 100}%` : '0%',
                      backgroundColor: getClassificationColor(d.classification)
                    }}
                  />
                </div>
                <div className="w-16 text-sm font-mono text-right">
                  {d.count}개 ({totalCount > 0 ? ((d.count / totalCount) * 100).toFixed(1) : 0}%)
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* 12개월 추이 */}
      <Card title="12개월 자산건전성 분류 추이">
        <StackedAreaChart
          data={trend}
          xAxisKey="label"
          areas={[
            { key: 'LOSS', name: '추정손실', color: '#dc2626', stackId: 'stack' },
            { key: 'DOUBTFUL', name: '회수의문', color: '#ef4444', stackId: 'stack' },
            { key: 'SUBSTANDARD', name: '고정', color: '#f97316', stackId: 'stack' },
            { key: 'PRECAUTIONARY', name: '요주의', color: '#f59e0b', stackId: 'stack' },
            { key: 'NORMAL', name: '정상', color: '#10b981', stackId: 'stack' },
          ]}
          height={280}
        />
      </Card>

      {/* 정상 외 기업 목록 */}
      <Card title="정상 외 분류 기업 목록" subtitle="부실 위험 기업 현황" noPadding>
        <Table
          columns={columns}
          data={list}
          emptyMessage="정상 외 분류 기업이 없습니다"
        />
      </Card>
    </div>
  );
}

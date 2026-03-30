import React, { useEffect, useState } from 'react';
import { Card, StatCard, DonutChart, COLORS } from '../components';
import Table from '../components/Table';
import { workoutApi } from '../utils/api';
import { formatEok, formatNumber, formatPercent, formatYm, getStatusColorClass } from '../utils/format';
import { Briefcase } from 'lucide-react';

export default function Workout() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<any>(null);
  const [list, setList] = useState<any[]>([]);
  const [scenarioSummary, setScenarioSummary] = useState<any>(null);
  const [selectedWorkout, setSelectedWorkout] = useState<any>(null);
  const [workoutScenarios, setWorkoutScenarios] = useState<any>(null);
  const [scenariosLoading, setScenariosLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [summaryRes, listRes, scenarioRes] = await Promise.all([
        workoutApi.getSummary(),
        workoutApi.getList(),
        workoutApi.getScenarioSummary(),
      ]);
      setSummary(summaryRes.data);
      setList(listRes.data || []);
      setScenarioSummary(scenarioRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRowClick = async (row: any) => {
    if (selectedWorkout?.workout_id === row.workout_id) {
      setSelectedWorkout(null);
      setWorkoutScenarios(null);
      return;
    }
    setSelectedWorkout(row);
    setScenariosLoading(true);
    try {
      const res = await workoutApi.getScenarios(row.workout_id);
      setWorkoutScenarios(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setScenariosLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const typeDonut = (summary?.by_type || []).map((d: any, i: number) => ({
    name: d.workout_type,
    value: d.count,
    color: COLORS.palette[i % COLORS.palette.length],
  }));

  const outcomeDonut = (summary?.by_outcome || []).map((d: any, i: number) => ({
    name: d.outcome,
    value: d.count,
    color: d.outcome === 'COMPLETED' ? COLORS.success :
           d.outcome === 'ONGOING' ? COLORS.warning :
           d.outcome === 'FAILED' ? COLORS.danger : COLORS.gray,
  }));

  const listColumns = [
    { key: 'company_name', header: '기업명', width: '150px' },
    { key: 'workout_type', header: 'Workout 유형', width: '120px' },
    { key: 'workout_start_ym', header: '시작월', width: '80px', render: (v: number) => formatYm(v) },
    {
      key: 'original_balance_억', header: '원금(억)', width: '80px', align: 'right' as const,
      render: (v: number) => <span className="font-mono">{v != null ? formatNumber(v, 1) : '-'}</span>
    },
    {
      key: 'recovery_rate', header: '회수율', width: '80px', align: 'right' as const,
      render: (v: number) => <span className={`font-mono font-semibold ${v >= 0.5 ? 'text-green-600' : v >= 0.3 ? 'text-yellow-600' : 'text-red-600'}`}>{formatPercent(v * 100)}</span>
    },
    {
      key: 'outcome', header: '결과', width: '90px', align: 'center' as const,
      render: (v: string) => (
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColorClass(v)}`}>{v}</span>
      )
    },
    { key: 'firm_size_cd', header: '규모', width: '70px', align: 'center' as const },
    { key: 'industry_cd', header: '업종', width: '70px', align: 'center' as const },
  ];

  const scenarioTypeStyle: Record<string, { bg: string; text: string; border: string; label: string }> = {
    OPTIMISTIC:  { bg: 'bg-green-50',  text: 'text-green-800',  border: 'border-green-200', label: '낙관적' },
    BASE:        { bg: 'bg-blue-50',   text: 'text-blue-800',   border: 'border-blue-200',  label: '기본'   },
    PESSIMISTIC: { bg: 'bg-red-50',    text: 'text-red-800',    border: 'border-red-200',   label: '비관적' },
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">NPL/Workout 관리</h1>
        <p className="text-sm text-gray-500 mt-1">부실채권 관리 및 회수 현황</p>
      </div>

      {/* StatCards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <StatCard
          title="총 Workout 건수"
          value={summary?.total_cases || 0}
          subtitle="전체 처리 건수"
          icon={<Briefcase size={20} />}
          color="blue"
        />
        <StatCard
          title="평균 회수율"
          value={formatPercent((summary?.avg_recovery_rate || 0) * 100)}
          subtitle="전체 Workout 평균"
          color="green"
        />
      </div>

      {/* 유형별 + 결과별 도넛 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Workout 유형 분포">
          <DonutChart
            data={typeDonut}
            height={250}
            centerText="유형별"
          />
        </Card>
        <Card title="Workout 결과 분포">
          <DonutChart
            data={outcomeDonut}
            height={250}
            centerText="결과별"
          />
        </Card>
      </div>

      {/* Workout 유형별 상세 */}
      <Card title="유형별 회수율 상세">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-left">유형</th>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-right">건수</th>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-right">평균 회수율</th>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-right">원금 총계(억)</th>
              </tr>
            </thead>
            <tbody>
              {(summary?.by_type || []).map((t: any, i: number) => (
                <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{t.workout_type}</td>
                  <td className="px-4 py-3 font-mono text-right">{t.count}</td>
                  <td className="px-4 py-3 font-mono text-right">
                    <span className={t.avg_recovery_rate >= 0.5 ? 'text-green-600 font-semibold' : 'text-red-600'}>
                      {formatPercent(t.avg_recovery_rate * 100)}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-right">{formatNumber(t.total_balance_억 ?? 0, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* 회수 시나리오 분석 */}
      {scenarioSummary && (
        <Card title="회수 시나리오 분석">
          <div className="mb-4 grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
              <p className="text-xs text-green-600 font-medium">낙관적 총 회수(억)</p>
              <p className="text-lg font-bold text-green-700 font-mono">{formatNumber(scenarioSummary.total_optimistic ?? 0, 1)}</p>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center">
              <p className="text-xs text-blue-600 font-medium">기본 총 회수(억)</p>
              <p className="text-lg font-bold text-blue-700 font-mono">{formatNumber(scenarioSummary.total_base ?? 0, 1)}</p>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
              <p className="text-xs text-red-600 font-medium">비관적 총 회수(억)</p>
              <p className="text-lg font-bold text-red-700 font-mono">{formatNumber(scenarioSummary.total_pessimistic ?? 0, 1)}</p>
            </div>
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 text-center">
              <p className="text-xs text-purple-600 font-medium">가중평균 기대(억)</p>
              <p className="text-lg font-bold text-purple-700 font-mono">{formatNumber(scenarioSummary.total_weighted_recovery ?? 0, 1)}</p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-left">방법</th>
                  <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-right">건수</th>
                  <th className="px-4 py-3 bg-green-50 font-semibold text-green-700 border-b text-right">낙관적(억)</th>
                  <th className="px-4 py-3 bg-blue-50 font-semibold text-blue-700 border-b text-right">기본(억)</th>
                  <th className="px-4 py-3 bg-red-50 font-semibold text-red-700 border-b text-right">비관적(억)</th>
                  <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-right">가중평균(억)</th>
                  <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-right">평균 NPV(억)</th>
                </tr>
              </thead>
              <tbody>
                {(scenarioSummary.by_method || []).map((m: any, i: number) => (
                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{m.method}</td>
                    <td className="px-4 py-3 font-mono text-right">{m.count}</td>
                    <td className="px-4 py-3 font-mono text-right text-green-700 font-semibold">{formatNumber(m.optimistic_recovery ?? 0, 1)}</td>
                    <td className="px-4 py-3 font-mono text-right text-blue-700 font-semibold">{formatNumber(m.base_recovery ?? 0, 1)}</td>
                    <td className="px-4 py-3 font-mono text-right text-red-700 font-semibold">{formatNumber(m.pessimistic_recovery ?? 0, 1)}</td>
                    <td className="px-4 py-3 font-mono text-right font-semibold">{formatNumber(m.weighted_expected ?? 0, 1)}</td>
                    <td className="px-4 py-3 font-mono text-right text-gray-600">{formatNumber(m.avg_npv ?? 0, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Workout 목록 */}
      <Card title="Workout 전체 목록 (행 클릭 시 시나리오 상세)" noPadding>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                {listColumns.map((col) => (
                  <th
                    key={col.key}
                    className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-left whitespace-nowrap"
                    style={{ width: col.width, textAlign: (col as any).align || 'left' }}
                  >
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {list.map((row, i) => (
                <React.Fragment key={row.workout_id}>
                  <tr
                    className={`border-b border-gray-100 cursor-pointer transition-colors ${
                      selectedWorkout?.workout_id === row.workout_id
                        ? 'bg-blue-50'
                        : 'hover:bg-gray-50'
                    }`}
                    onClick={() => handleRowClick(row)}
                  >
                    {listColumns.map((col) => (
                      <td
                        key={col.key}
                        className="px-4 py-3"
                        style={{ textAlign: (col as any).align || 'left' }}
                      >
                        {(col as any).render ? (col as any).render((row as any)[col.key]) : (row as any)[col.key]}
                      </td>
                    ))}
                  </tr>
                  {/* 시나리오 패널 */}
                  {selectedWorkout?.workout_id === row.workout_id && (
                    <tr>
                      <td colSpan={listColumns.length} className="bg-gray-50 px-4 py-4 border-b">
                        {scenariosLoading ? (
                          <div className="flex items-center gap-2 text-sm text-gray-500">
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                            시나리오 로딩 중...
                          </div>
                        ) : workoutScenarios ? (
                          <div>
                            <p className="text-xs font-semibold text-gray-600 mb-3">
                              회수 시나리오 분석: {row.company_name} ({row.workout_type})
                            </p>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                              {workoutScenarios.scenarios.map((s: any) => {
                                const style = scenarioTypeStyle[s.scenario_type] || scenarioTypeStyle.BASE;
                                return (
                                  <div key={s.scenario_type} className={`${style.bg} border ${style.border} rounded-lg p-3`}>
                                    <div className="flex items-center justify-between mb-2">
                                      <span className={`text-sm font-bold ${style.text}`}>{style.label}</span>
                                      <span className={`text-xs px-2 py-0.5 rounded-full ${style.bg} ${style.text} border ${style.border}`}>
                                        확률 {s.probability_pct}%
                                      </span>
                                    </div>
                                    <div className="space-y-1 text-sm">
                                      <div className="flex justify-between">
                                        <span className="text-gray-500">회수금액</span>
                                        <span className="font-mono font-semibold">{formatEok(s.recovery_amount_억 ?? 0)}</span>
                                      </div>
                                      <div className="flex justify-between">
                                        <span className="text-gray-500">기간</span>
                                        <span className="font-mono">{s.recovery_timeline_months}개월</span>
                                      </div>
                                      <div className="flex justify-between">
                                        <span className="text-gray-500">NPV</span>
                                        <span className="font-mono">{formatEok(s.npv_억 ?? 0)}</span>
                                      </div>
                                      <div className="flex justify-between">
                                        <span className="text-gray-500">IRR</span>
                                        <span className="font-mono">{s.irr_pct?.toFixed(1)}%</span>
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                            <div className="mt-3 pt-3 border-t border-gray-200 flex items-center justify-between">
                              <span className="text-sm text-gray-600">가중평균 기대 회수액</span>
                              <span className="text-base font-bold text-purple-700 font-mono">
                                {formatEok(workoutScenarios.weighted_expected_recovery_억 ?? 0, 2)}
                              </span>
                            </div>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
              {list.length === 0 && (
                <tr>
                  <td colSpan={listColumns.length} className="px-4 py-8 text-center text-gray-400">
                    Workout 데이터가 없습니다
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

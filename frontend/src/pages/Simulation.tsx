import React, { useEffect, useState } from 'react';
import { Card, StatCard, GroupedBarChart, COLORS } from '../components';
import { modelPerfApi, ewsApi } from '../utils/api';
import { getEWSGradeBgClass, getEWSGradeColor, formatYm } from '../utils/format';
import { Activity } from 'lucide-react';

export default function Simulation() {
  const [loading, setLoading] = useState(true);
  const [leadTime, setLeadTime] = useState<any>(null);
  const [defaultCompanies, setDefaultCompanies] = useState<any[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<any>(null);
  const [companyHistory, setCompanyHistory] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const leadRes = await modelPerfApi.getLeadTime();
      setLeadTime(leadRes.data);
      // Detail list of defaulted companies
      if (leadRes.data?.detail) {
        setDefaultCompanies(leadRes.data.detail);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCompany = async (item: any) => {
    setSelectedCompany(item);
    setHistoryLoading(true);
    try {
      const res = await ewsApi.getCompanyHistory(item.borrower_id);
      setCompanyHistory(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setHistoryLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const leadDistData = (leadTime?.distribution || []).map((d: any) => ({
    name: `${d.lead_months}M`,
    count: d.count,
  }));

  // EWS grade timeline for selected company
  const gradeColors: Record<string, string> = {
    A: getEWSGradeColor('A'),
    B: getEWSGradeColor('B'),
    C: getEWSGradeColor('C'),
    D: getEWSGradeColor('D'),
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">부실탐지 시뮬레이션</h1>
        <p className="text-sm text-gray-500 mt-1">부도 기업의 EWS 경보 타임라인 분석</p>
      </div>

      {/* StatCards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="분석 부도 기업"
          value={leadTime?.total_defaulted || 0}
          subtitle="선행 시간 데이터 보유"
          icon={<Activity size={20} />}
          color="red"
        />
        <StatCard
          title="평균 선행 시간"
          value={`${leadTime?.avg_lead_months || 0}개월`}
          subtitle="부도 전 D등급 최초 경보"
          color="yellow"
        />
        <StatCard
          title="최대 선행 시간"
          value={`${leadTime?.max_lead_months || 0}개월`}
          subtitle="가장 조기에 탐지된 부도"
          color="blue"
        />
      </div>

      {/* 선행 시간 분포 차트 */}
      <Card title="부도 전 EWS D등급 선행 시간 분포">
        <GroupedBarChart
          data={leadDistData}
          xAxisKey="name"
          bars={[{ key: 'count', name: '기업 수', color: COLORS.danger }]}
          height={250}
          showLegend={false}
        />
        <p className="text-xs text-gray-500 mt-2 text-center">
          X축: 부도 발생 전 EWS D등급 최초 경보 시점 (개월 수)
        </p>
      </Card>

      {/* 부도 기업 목록 + 타임라인 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* 기업 목록 */}
        <Card title="부도 기업 목록" subtitle="클릭하여 EWS 타임라인 보기">
          <div className="space-y-1 max-h-96 overflow-y-auto">
            {defaultCompanies.map((item: any, i: number) => (
              <button
                key={i}
                onClick={() => handleSelectCompany(item)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                  selectedCompany?.borrower_id === item.borrower_id
                    ? 'bg-blue-50 border border-blue-200'
                    : 'hover:bg-gray-50'
                }`}
              >
                <div className="flex justify-between items-center">
                  <span className="font-medium text-gray-900">{item.borrower_id}</span>
                  <span className="text-xs text-red-600 font-semibold">
                    {item.lead_months}개월 전
                  </span>
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  첫 경보: {formatYm(item.first_signal_ym)} | 부도: {formatYm(item.default_ym)}
                </div>
              </button>
            ))}
          </div>
        </Card>

        {/* EWS 타임라인 */}
        <div className="lg:col-span-2">
          {selectedCompany ? (
            <Card
              title={`${selectedCompany.borrower_id} EWS 타임라인`}
              subtitle={`부도월: ${formatYm(selectedCompany.default_ym)} | 선행 시간: ${selectedCompany.lead_months}개월`}
            >
              {historyLoading ? (
                <div className="flex items-center justify-center h-32">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
              ) : (
                <div>
                  {/* EWS Grade 타임라인 바 */}
                  <div className="mb-4">
                    <p className="text-xs text-gray-500 mb-2">월별 EWS 등급 추이</p>
                    <div className="flex flex-wrap gap-1">
                      {companyHistory.map((h: any, i: number) => (
                        <div
                          key={i}
                          className="flex flex-col items-center"
                          title={`${formatYm(h.ym)}: ${h.ews_grade}등급 (${h.ews_score?.toFixed(1)}점)`}
                        >
                          <div
                            className="w-6 h-8 rounded-sm flex items-end justify-center text-xs font-bold text-white"
                            style={{
                              backgroundColor: gradeColors[h.ews_grade] || '#6b7280',
                              opacity: h.ym === selectedCompany.default_ym ? 1 : 0.75
                            }}
                          >
                            {h.ews_grade}
                          </div>
                          {i % 6 === 0 && (
                            <span className="text-xs text-gray-400 mt-1" style={{ fontSize: '9px' }}>
                              {String(h.ym).slice(2, 4)}/{String(h.ym).slice(4)}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-4 mt-3">
                      {['A', 'B', 'C', 'D'].map(g => (
                        <div key={g} className="flex items-center gap-1">
                          <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: gradeColors[g] }}></div>
                          <span className="text-xs text-gray-600">{g}등급</span>
                        </div>
                      ))}
                      {selectedCompany.default_ym && (
                        <div className="ml-auto text-xs text-red-600 font-semibold">
                          부도월: {formatYm(selectedCompany.default_ym)}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 상세 테이블 */}
                  <div className="overflow-x-auto max-h-48">
                    <table className="w-full text-xs">
                      <thead>
                        <tr>
                          <th className="px-2 py-2 bg-gray-50 font-semibold text-gray-700 border-b text-left">기준월</th>
                          <th className="px-2 py-2 bg-gray-50 font-semibold text-gray-700 border-b text-center">EWS등급</th>
                          <th className="px-2 py-2 bg-gray-50 font-semibold text-gray-700 border-b text-right">EWS점수</th>
                          <th className="px-2 py-2 bg-gray-50 font-semibold text-gray-700 border-b text-center">Stage</th>
                          <th className="px-2 py-2 bg-gray-50 font-semibold text-gray-700 border-b text-right">연체일</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...companyHistory].reverse().map((h: any, i: number) => (
                          <tr
                            key={i}
                            className={`border-b border-gray-100 ${
                              h.ym === selectedCompany.default_ym ? 'bg-red-50 font-semibold' : 'hover:bg-gray-50'
                            }`}
                          >
                            <td className="px-2 py-1.5">{formatYm(h.ym)}</td>
                            <td className="px-2 py-1.5 text-center">
                              <span className={`px-1.5 py-0.5 rounded text-xs font-semibold ${getEWSGradeBgClass(h.ews_grade)}`}>
                                {h.ews_grade}
                              </span>
                            </td>
                            <td className="px-2 py-1.5 font-mono text-right">{h.ews_score?.toFixed(1)}</td>
                            <td className="px-2 py-1.5 text-center">{h.ifrs9_stage}</td>
                            <td className="px-2 py-1.5 font-mono text-right">{h.principal_past_due_days}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </Card>
          ) : (
            <Card>
              <div className="flex items-center justify-center h-48 text-gray-400">
                <div className="text-center">
                  <Activity size={40} className="mx-auto mb-3 opacity-30" />
                  <p>좌측에서 부도 기업을 선택하면<br />EWS 타임라인이 표시됩니다</p>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

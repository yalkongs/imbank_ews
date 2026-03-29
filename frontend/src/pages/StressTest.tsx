import React, { useState, useEffect } from 'react';
import { Zap, AlertTriangle, BarChart2 } from 'lucide-react';
import { stressTestApi } from '../utils/api';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts';

interface Scenario {
  scenario_id: string;
  scenario_name: string;
  description: string;
  rate_shock_bps: number;
  gdp_shock_pct: number;
  credit_spread_bps: number;
  base_pd_multiplier: number;
  base_lgd_multiplier: number;
  expected_npl_ratio_pct: number;
  expected_ecl_change_pct: number;
}

const SCENARIO_COLORS: Record<string, string> = {
  BASE: 'border-green-300 bg-green-50',
  ADVERSE: 'border-yellow-300 bg-yellow-50',
  SEVERE: 'border-red-300 bg-red-50',
};

const SCENARIO_LABEL_COLOR: Record<string, string> = {
  BASE: 'text-green-700',
  ADVERSE: 'text-yellow-700',
  SEVERE: 'text-red-700',
};

export default function StressTest() {
  const [activeTab, setActiveTab] = useState<'scenario' | 'custom'>('scenario');
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedSc, setSelectedSc] = useState<string | null>(null);
  const [impact, setImpact] = useState<any>(null);
  const [impactLoading, setImpactLoading] = useState(false);

  // 사용자 정의
  const [rateShock, setRateShock] = useState(0);
  const [gdpShock, setGdpShock]   = useState(0);
  const [spreadShock, setSpreadShock] = useState(0);
  const [customResult, setCustomResult] = useState<any>(null);
  const [customLoading, setCustomLoading] = useState(false);

  useEffect(() => {
    stressTestApi.getScenarios().then(r => setScenarios(r.data));
  }, []);

  function runScenario(id: string) {
    setSelectedSc(id);
    setImpactLoading(true);
    stressTestApi.getImpact(id).then(r => {
      setImpact(r.data);
      setImpactLoading(false);
    });
  }

  function runCustom() {
    setCustomLoading(true);
    stressTestApi.getCustom({
      rate_shock_bps: rateShock,
      gdp_shock_pct: gdpShock,
      credit_spread_bps: spreadShock,
    }).then(r => {
      setCustomResult(r.data);
      setCustomLoading(false);
    });
  }

  const compareData = scenarios.map(sc => ({
    name: sc.scenario_name,
    ecl_change: sc.expected_ecl_change_pct,
    npl: sc.expected_npl_ratio_pct,
  }));

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">스트레스 테스트</h1>

      {/* 탭 */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-xl w-fit">
        {[
          { key: 'scenario' as const, label: '시나리오별 분석' },
          { key: 'custom' as const, label: '사용자 정의' },
        ].map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === t.key ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'scenario' ? (
        <>
          {/* 시나리오 카드 */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            {scenarios.map(sc => (
              <div key={sc.scenario_id}
                className={`border-2 rounded-xl p-5 ${SCENARIO_COLORS[sc.scenario_id] ?? 'border-gray-200 bg-white'}`}>
                <h3 className={`text-base font-bold mb-1 ${SCENARIO_LABEL_COLOR[sc.scenario_id] ?? 'text-gray-900'}`}>
                  {sc.scenario_name}
                </h3>
                <p className="text-xs text-gray-600 mb-3">{sc.description}</p>
                <div className="space-y-1 text-sm text-gray-700 mb-4">
                  <div className="flex justify-between">
                    <span className="text-gray-500">금리 충격</span>
                    <span className="font-medium">{sc.rate_shock_bps > 0 ? '+' : ''}{sc.rate_shock_bps} bps</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">GDP 충격</span>
                    <span className="font-medium">{sc.gdp_shock_pct > 0 ? '+' : ''}{sc.gdp_shock_pct}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">예상 NPL 비율</span>
                    <span className="font-semibold text-red-600">{sc.expected_npl_ratio_pct}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">ECL 변화</span>
                    <span className="font-semibold text-red-600">+{sc.expected_ecl_change_pct}%</span>
                  </div>
                </div>
                <button
                  onClick={() => runScenario(sc.scenario_id)}
                  className={`w-full py-2 rounded-lg text-sm font-medium transition-colors ${
                    selectedSc === sc.scenario_id
                      ? 'bg-blue-600 text-white'
                      : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  분석 실행
                </button>
              </div>
            ))}
          </div>

          {/* 시나리오 비교 차트 */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">ECL 변화율 비교 (%)</h3>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={compareData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} unit="%" />
                  <Tooltip />
                  <Bar dataKey="ecl_change" name="ECL 변화율" radius={[4,4,0,0]}>
                    {compareData.map((_, i) => (
                      <Cell key={i} fill={['#16a34a','#f59e0b','#dc2626'][i]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">NPL 비율 비교 (%)</h3>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={compareData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} unit="%" />
                  <Tooltip />
                  <Bar dataKey="npl" name="NPL 비율" radius={[4,4,0,0]}>
                    {compareData.map((_, i) => (
                      <Cell key={i} fill={['#16a34a','#f59e0b','#dc2626'][i]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 분석 결과 */}
          {impactLoading && <div className="text-center py-10 text-gray-400">분석 중...</div>}
          {impact && !impactLoading && (
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-4">포트폴리오 충격 분석 결과</h3>
              <div className="grid grid-cols-4 gap-4 mb-5">
                {[
                  { label: '현재 ECL', value: `${impact.portfolio_impact.current_ecl_억}억` },
                  { label: '스트레스 ECL', value: `${impact.portfolio_impact.stressed_ecl_억}억`, accent: true },
                  { label: 'ECL 증가액', value: `+${impact.portfolio_impact.ecl_increase_억}억`, accent: true },
                  { label: '예상 NPL', value: `${impact.portfolio_impact.stressed_npl_pct}%`, accent: true },
                ].map(s => (
                  <div key={s.label} className={`text-center p-3 rounded-xl ${s.accent ? 'bg-red-50' : 'bg-gray-50'}`}>
                    <p className="text-xs text-gray-500 mb-1">{s.label}</p>
                    <p className={`text-lg font-bold ${s.accent ? 'text-red-600' : 'text-gray-900'}`}>{s.value}</p>
                  </div>
                ))}
              </div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">업종별 영향도</h4>
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    {['업종','현재 ECL(억)','스트레스 ECL(억)','ECL 증가율'].map(h => (
                      <th key={h} className="px-3 py-2 text-left text-xs text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {impact.industry_impact.slice(0, 10).map((ind: any) => (
                    <tr key={ind.industry_cd}>
                      <td className="px-3 py-2">{ind.industry_name}</td>
                      <td className="px-3 py-2">{ind.current_ecl_억}</td>
                      <td className="px-3 py-2">{ind.stressed_ecl_억}</td>
                      <td className={`px-3 py-2 font-medium ${ind.ecl_increase_pct > 80 ? 'text-red-600' : ind.ecl_increase_pct > 50 ? 'text-orange-500' : 'text-gray-700'}`}>
                        +{ind.ecl_increase_pct}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : (
        /* 사용자 정의 탭 */
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-5">파라미터 설정</h3>
            <div className="space-y-6">
              {[
                { label: `금리 충격: ${rateShock} bps`, min: -200, max: 600, value: rateShock, onChange: setRateShock },
                { label: `GDP 성장률 변화: ${gdpShock}%`, min: -8, max: 3, step: 0.5, value: gdpShock, onChange: setGdpShock },
                { label: `신용스프레드: ${spreadShock} bps`, min: 0, max: 500, value: spreadShock, onChange: setSpreadShock },
              ].map(s => (
                <div key={s.label}>
                  <div className="flex justify-between mb-2">
                    <span className="text-sm text-gray-700">{s.label}</span>
                  </div>
                  <input type="range" min={s.min} max={s.max} step={s.step ?? 1} value={s.value}
                    onChange={e => s.onChange(Number(e.target.value))}
                    className="w-full accent-blue-600" />
                  <div className="flex justify-between text-xs text-gray-400 mt-1">
                    <span>{s.min}</span><span>{s.max}</span>
                  </div>
                </div>
              ))}
              <button onClick={runCustom}
                className="w-full py-2.5 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors">
                즉시 계산
              </button>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">계산 결과</h3>
            {customLoading && <div className="text-center py-10 text-gray-400">계산 중...</div>}
            {customResult && !customLoading && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: 'PD 배수', value: customResult.params.pd_multiplier?.toFixed(2) },
                    { label: 'LGD 배수', value: customResult.params.lgd_multiplier?.toFixed(2) },
                    { label: '스트레스 ECL', value: `${customResult.portfolio_impact.stressed_ecl_억}억` },
                    { label: '예상 NPL', value: `${customResult.portfolio_impact.stressed_npl_pct}%` },
                  ].map(s => (
                    <div key={s.label} className="bg-red-50 p-3 rounded-xl text-center">
                      <p className="text-xs text-gray-500">{s.label}</p>
                      <p className="text-lg font-bold text-red-600">{s.value}</p>
                    </div>
                  ))}
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-2">포트폴리오 ECL 변화</p>
                  <div className="relative bg-gray-200 rounded-full h-6 overflow-hidden">
                    <div className="h-full bg-red-500 rounded-full transition-all"
                      style={{ width: `${Math.min(customResult.portfolio_impact.ecl_increase_pct / 200 * 100, 100)}%` }} />
                    <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-white">
                      +{customResult.portfolio_impact.ecl_increase_pct}%
                    </span>
                  </div>
                </div>
              </div>
            )}
            {!customResult && !customLoading && (
              <div className="text-center py-10 text-gray-400 text-sm">
                좌측에서 파라미터를 설정하고 계산 버튼을 누르세요
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

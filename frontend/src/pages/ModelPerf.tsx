import React, { useEffect, useState } from 'react';
import { Card, StatCard, GroupedBarChart, COLORS } from '../components';
import { modelPerfApi } from '../utils/api';
import { formatYm } from '../utils/format';
import { Brain, AlertTriangle, RefreshCw, Lock, CheckCircle, ChevronDown, ChevronUp } from 'lucide-react';

// ─── 재학습 모달 ─────────────────────────────────────────────────────────────
function RetrainModal({
  tier,
  tierLabel,
  onClose,
  onSuccess,
}: {
  tier: string;
  tierLabel: string;
  onClose: () => void;
  onSuccess: (msg: string) => void;
}) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await modelPerfApi.retrain(tier, password);
      onSuccess(res.data.message || '재학습이 완료되었습니다.');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || '재학습 중 오류가 발생했습니다.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6">
        <div className="flex items-center gap-2 mb-4">
          <Lock size={20} className="text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-900">모델 재학습 — {tierLabel}</h3>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          재학습을 실행하려면 관리자 비밀번호를 입력하세요.
          POC 환경에서는 Tier 메타데이터 기반 모델 재생성이 실행됩니다.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">관리자 비밀번호</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm
                         focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="비밀번호 입력"
              autoFocus
            />
          </div>
          {error && (
            <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded">{error}</p>
          )}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700
                         hover:bg-gray-50"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={loading || !password}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium
                         hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                         flex items-center justify-center gap-2"
            >
              {loading ? (
                <><span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />재학습 중...</>
              ) : (
                <><RefreshCw size={14} />재학습 실행</>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Tier 모델 카드 ────────────────────────────────────────────────────────────
const TIER_BADGE_STYLE: Record<string, string> = {
  T1: 'bg-green-100 text-green-700 border border-green-200',
  T2: 'bg-blue-100 text-blue-700 border border-blue-200',
  T3: 'bg-gray-100 text-gray-600 border border-gray-200',
};

function TierModelCard({
  tierKey,
  data,
  onRetrain,
}: {
  tierKey: string;
  data: any;
  onRetrain: (tier: string, label: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const tier = data.tier || tierKey.toUpperCase();
  const badgeStyle = TIER_BADGE_STYLE[tier] || 'bg-gray-100 text-gray-600';

  const performanceColor = (val: number, thresholds: [number, number]) => {
    if (val >= thresholds[1]) return 'text-green-600';
    if (val >= thresholds[0]) return 'text-blue-600';
    return 'text-orange-500';
  };

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      {/* 헤더 */}
      <div className="bg-gray-50 px-5 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`px-2.5 py-1 rounded-lg text-sm font-bold ${badgeStyle}`}>
            {tier}
          </span>
          <div>
            <p className="font-semibold text-gray-900">{data.tier_label || '—'}</p>
            <p className="text-xs text-gray-500 mt-0.5">{data.description || ''}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {data.file_exists !== false && (
            <button
              onClick={() => onRetrain(tierKey, data.tier_label || tier)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600
                         border border-gray-300 rounded-lg hover:bg-gray-100"
            >
              <RefreshCw size={13} />재학습
            </button>
          )}
          <button
            onClick={() => setExpanded(v => !v)}
            className="p-1.5 text-gray-400 hover:text-gray-600"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {/* 성능 지표 요약 */}
      <div className="px-5 py-4 grid grid-cols-4 gap-4">
        <div className="text-center">
          <p className="text-xs text-gray-500 mb-1">AUROC</p>
          <p className={`text-xl font-bold font-mono ${performanceColor(data.avg_auroc || 0, [0.80, 0.85])}`}>
            {(data.avg_auroc || 0).toFixed(4)}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500 mb-1">KS</p>
          <p className={`text-xl font-bold font-mono ${performanceColor(data.avg_ks || 0, [0.55, 0.62])}`}>
            {(data.avg_ks || 0).toFixed(4)}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500 mb-1">AP</p>
          <p className="text-xl font-bold font-mono text-gray-700">
            {(data.avg_ap || 0).toFixed(4)}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500 mb-1">대상 기업</p>
          <p className="text-xl font-bold text-gray-700">
            {(data.target_company_count || 0).toLocaleString()}개
          </p>
        </div>
      </div>

      {/* 확장 영역 */}
      {expanded && (
        <div className="px-5 pb-5 border-t border-gray-100 pt-4 space-y-4">
          {/* 데이터 특성 */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">데이터 특성</p>
              <div className="space-y-1.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">데이터 완성도</span>
                  <span className="font-medium">{data.data_completeness_range || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">기업 규모</span>
                  <span className="font-medium">{(data.firm_size || []).join(', ')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">검증 Fold 수</span>
                  <span className="font-medium">{data.n_folds || 12}개</span>
                </div>
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">주요 예측 피처 (Top 10)</p>
              <div className="flex flex-wrap gap-1">
                {(data.top_features || []).map((f: string, i: number) => (
                  <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded font-mono">
                    {f}
                  </span>
                ))}
              </div>
            </div>
          </div>
          {/* 모델 특이사항 */}
          {data.notes && (
            <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-800">
              {data.notes}
            </div>
          )}
          {data.is_poc_model && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700">
              이 모델은 검증용 환경에서 챔피언 모델 기반으로 생성된 POC 모델입니다.
              실제 운영 적용 전 Tier 별 학습 데이터로 재학습이 필요합니다.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── 메인 컴포넌트 ─────────────────────────────────────────────────────────────
export default function ModelPerf() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<any>(null);
  const [confusion, setConfusion] = useState<any>(null);
  const [leadTime, setLeadTime] = useState<any>(null);
  const [tierModels, setTierModels] = useState<any>(null);

  // 재학습 모달
  const [retrainTarget, setRetrainTarget] = useState<{ tier: string; label: string } | null>(null);
  const [retrainSuccess, setRetrainSuccess] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [summaryRes, confRes, leadRes, tierRes] = await Promise.all([
        modelPerfApi.getSummary(),
        modelPerfApi.getConfusion(),
        modelPerfApi.getLeadTime(),
        modelPerfApi.getTierModels(),
      ]);
      setSummary(summaryRes.data);
      setConfusion(confRes.data);
      setLeadTime(leadRes.data);
      setTierModels(tierRes.data);
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

  const leadDistData = (leadTime?.distribution || []).map((d: any) => ({
    name: `${d.lead_months}개월`,
    count: d.count,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">모델 성능</h1>
        <p className="text-sm text-gray-500 mt-1">Walk-Forward 12-Fold 검증 결과 · Tier 별 모델 현황</p>
      </div>

      {/* 재학습 성공 메시지 */}
      {retrainSuccess && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start gap-3">
          <CheckCircle size={18} className="text-green-600 mt-0.5 shrink-0" />
          <div className="text-sm text-green-800">
            <p className="font-semibold mb-0.5">재학습 완료</p>
            <p>{retrainSuccess}</p>
          </div>
          <button onClick={() => setRetrainSuccess('')} className="ml-auto text-green-500 hover:text-green-700 text-xs">닫기</button>
        </div>
      )}

      {/* 합성 데이터 면책 조항 */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3">
        <AlertTriangle size={20} className="text-amber-600 mt-0.5 flex-shrink-0" />
        <div className="text-sm text-amber-800">
          <p className="font-semibold mb-1">합성 데이터 학습 결과 — AUROC 해석 주의</p>
          <p>
            이 모델은 시뮬레이션 목적으로 생성된 합성 데이터로 학습되었습니다.
            합성 데이터 생성 과정에서 <strong>미래 부도 시점(months_to_def)</strong>을
            이용한 <code className="bg-amber-100 px-1 rounded">risk_factor</code>가
            재무비율·법적리스크·행동신호 등 거의 모든 피처에 반영되어 있습니다.
            이로 인해 AUROC가 실제보다 높게 나타나는 <strong>Oracle 오염(Data Leakage)</strong> 현상입니다.
          </p>
          <p className="mt-1">
            실제 금융기관 데이터 기반 EWS 모델의 기대 성능: <strong>AUROC 0.80~0.88 / KS 0.50~0.60</strong>
          </p>
        </div>
      </div>

      {/* StatCards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="평균 AUROC"
          value={(summary?.avg_auroc || 0).toFixed(4)}
          subtitle={`${summary?.n_folds || 0} Fold 평균`}
          icon={<Brain size={20} />}
          color="blue"
        />
        <StatCard
          title="평균 KS"
          value={(summary?.avg_ks || 0).toFixed(4)}
          subtitle="Kolmogorov-Smirnov"
          color="green"
        />
        <StatCard
          title="평균 AP"
          value={(summary?.avg_ap || 0).toFixed(4)}
          subtitle="Average Precision"
          color="blue"
        />
        <StatCard
          title="평균 선행 시간"
          value={`${leadTime?.avg_lead_months || 0}개월`}
          subtitle={`최대 ${leadTime?.max_lead_months || 0}개월 전 경보`}
          color="yellow"
        />
      </div>

      {/* ── T1/T2/T3 Tier 별 모델 ─────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-lg font-bold text-gray-900">Tier 별 모델 현황</h2>
            <p className="text-sm text-gray-500">기업 규모(대기업/중소중견/소기업)에 특화된 3종 EWS 모델</p>
          </div>
        </div>

        {/* Tier 모델 비교 요약 */}
        <div className="bg-gray-50 rounded-xl p-4 mb-4">
          <div className="grid grid-cols-3 gap-4 text-center text-sm">
            {['t1', 't2', 't3'].map(k => {
              const m = tierModels?.[k];
              if (!m) return null;
              return (
                <div key={k} className="space-y-1">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${TIER_BADGE_STYLE[m.tier || k.toUpperCase()]}`}>
                    {m.tier || k.toUpperCase()}
                  </span>
                  <p className="font-semibold text-gray-800">{m.tier_label}</p>
                  <p className="text-gray-500 text-xs">{m.data_completeness_range} 완성도</p>
                  <p className="font-mono font-bold text-green-600">AUROC {(m.avg_auroc || 0).toFixed(4)}</p>
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-3">
          {['t1', 't2', 't3'].map(k => {
            const m = tierModels?.[k];
            if (!m) return null;
            return (
              <TierModelCard
                key={k}
                tierKey={k}
                data={m}
                onRetrain={(tier, label) => setRetrainTarget({ tier, label })}
              />
            );
          })}
        </div>
      </div>

      {/* Fold별 성능 */}
      <Card title="Walk-Forward 12-Fold 성능 지표">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-center">Fold</th>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-left">학습 기간</th>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-left">검증 기간</th>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-right">AUROC</th>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-right">KS</th>
                <th className="px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b text-right">AP</th>
              </tr>
            </thead>
            <tbody>
              {(summary?.fold_metrics || []).map((f: any) => (
                <tr key={f.fold_id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 text-center font-medium">{f.fold_id}</td>
                  <td className="px-4 py-3 text-xs text-gray-600">{formatYm(f.train_start)} ~ {formatYm(f.train_end)}</td>
                  <td className="px-4 py-3 text-xs text-gray-600">{formatYm(f.test_start)} ~ {formatYm(f.test_end)}</td>
                  <td className="px-4 py-3 font-mono text-right text-green-600 font-semibold">{f.auroc.toFixed(4)}</td>
                  <td className="px-4 py-3 font-mono text-right">{f.ks.toFixed(4)}</td>
                  <td className="px-4 py-3 font-mono text-right">{f.ap.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* 혼동행렬 */}
      {confusion && (
        <Card
          title={`혼동행렬 (기준월: ${formatYm(confusion.ym)})`}
          subtitle={confusion.ym_note || 'EWS D등급 → 향후 6개월 내 부도 예측'}
        >
          <div className="grid grid-cols-2 gap-4 max-w-lg mx-auto">
            <div className="text-center">
              <p className="text-xs text-gray-500 mb-1">예측: D등급 / 실제: 부도</p>
              <div className="bg-green-100 border-2 border-green-400 rounded-lg p-6">
                <p className="text-3xl font-bold text-green-700">{confusion.tp}</p>
                <p className="text-sm text-green-600 mt-1">TP (정확 경보)</p>
              </div>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-500 mb-1">예측: D등급 / 실제: 정상</p>
              <div className="bg-yellow-100 border-2 border-yellow-400 rounded-lg p-6">
                <p className="text-3xl font-bold text-yellow-700">{confusion.fp}</p>
                <p className="text-sm text-yellow-600 mt-1">FP (오경보)</p>
              </div>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-500 mb-1">예측: 정상 / 실제: 부도</p>
              <div className="bg-red-100 border-2 border-red-400 rounded-lg p-6">
                <p className="text-3xl font-bold text-red-700">{confusion.fn}</p>
                <p className="text-sm text-red-600 mt-1">FN (미탐지)</p>
              </div>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-500 mb-1">예측: 정상 / 실제: 정상</p>
              <div className="bg-blue-100 border-2 border-blue-400 rounded-lg p-6">
                <p className="text-3xl font-bold text-blue-700">{confusion.tn}</p>
                <p className="text-sm text-blue-600 mt-1">TN (정확 정상)</p>
              </div>
            </div>
          </div>
          <div className="flex justify-center gap-6 mt-4 text-sm">
            <span>정밀도: <strong>{(confusion.precision * 100).toFixed(1)}%</strong></span>
            <span>재현율: <strong>{(confusion.recall * 100).toFixed(1)}%</strong></span>
            <span>F1: <strong>{(confusion.f1 * 100).toFixed(1)}%</strong></span>
          </div>
        </Card>
      )}

      {/* 선행 시간 분포 */}
      {leadTime && (
        <Card title="부도 전 EWS 경보 선행 시간 분포">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div className="bg-blue-50 rounded-lg p-3 text-center">
              <p className="text-sm text-gray-500">평균 선행 시간</p>
              <p className="text-2xl font-bold text-blue-700">{leadTime.avg_lead_months}개월</p>
            </div>
            <div className="bg-green-50 rounded-lg p-3 text-center">
              <p className="text-sm text-gray-500">최대 선행 시간</p>
              <p className="text-2xl font-bold text-green-700">{leadTime.max_lead_months}개월</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <p className="text-sm text-gray-500">총 부도 기업</p>
              <p className="text-2xl font-bold text-gray-700">{leadTime.total_defaulted}개</p>
            </div>
          </div>
          <GroupedBarChart
            data={leadDistData}
            xAxisKey="name"
            bars={[{ key: 'count', name: '기업 수', color: COLORS.primary }]}
            height={250}
            showLegend={false}
          />
        </Card>
      )}

      {/* 재학습 모달 */}
      {retrainTarget && (
        <RetrainModal
          tier={retrainTarget.tier}
          tierLabel={retrainTarget.label}
          onClose={() => setRetrainTarget(null)}
          onSuccess={msg => {
            setRetrainTarget(null);
            setRetrainSuccess(msg);
            loadData(); // 모델 정보 갱신
          }}
        />
      )}
    </div>
  );
}

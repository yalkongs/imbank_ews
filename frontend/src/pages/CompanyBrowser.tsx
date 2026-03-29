import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, TrendingUp, ChevronDown, ChevronRight, Building2, Cog, Package, MapPin } from 'lucide-react';
import { Card, TrendChart } from '../components';
import Table from '../components/Table';
import { companyApi, ewsApi, ewsAdvancedApi } from '../utils/api';
import { getEWSGradeBgClass, getEWSGradeColor, formatYm, getClassificationLabel, getStatusColorClass } from '../utils/format';

const TABS = ['EWS 신호', '여신 현황', '자산건전성', '담보 이력', 'ECL', '신용등급', '코베넌트', '거래행태', 'Workout 이력', '선행 신호'];

export default function CompanyBrowser() {
  const [searchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchRegion, setSearchRegion] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchFocused, setSearchFocused] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get('id'));
  const [companyDetail, setCompanyDetail] = useState<any>(null);
  const [ewsHistory, setEwsHistory] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [collateralValuation, setCollateralValuation] = useState<any[]>([]);
  const [expandedCollateral, setExpandedCollateral] = useState<string | null>(null);
  const [collateralHistory, setCollateralHistory] = useState<Record<string, any>>({});
  const [completeness, setCompleteness] = useState<any>(null);
  const [publicEvents, setPublicEvents] = useState<any[]>([]);
  const [newsData, setNewsData] = useState<any[]>([]);
  const [marketSignal, setMarketSignal] = useState<any>({ listed: false, data: [] });
  const [supplyChain, setSupplyChain] = useState<any[]>([]);
  const [advancedLoaded, setAdvancedLoaded] = useState(false);
  const [advancedLoading, setAdvancedLoading] = useState(false);

  useEffect(() => {
    const id = searchParams.get('id');
    if (id) {
      setSelectedId(id);
    }
  }, [searchParams]);

  useEffect(() => {
    if (selectedId) {
      loadCompanyDetail(selectedId);
    }
  }, [selectedId]);

  const handleSearch = async (q: string, region?: string) => {
    const r = region !== undefined ? region : searchRegion;
    setSearchQuery(q);
    setLoading(true);
    try {
      const res = await companyApi.search(q, r);
      setSearchResults(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRegionChange = (r: string) => {
    setSearchRegion(r);
    handleSearch(searchQuery, r);
  };

  const loadCompanyDetail = async (id: string) => {
    setDetailLoading(true);
    setExpandedCollateral(null);
    setCollateralHistory({});
    setCompleteness(null);
    setPublicEvents([]);
    setNewsData([]);
    setMarketSignal({ listed: false, data: [] });
    setSupplyChain([]);
    setAdvancedLoaded(false);
    try {
      const [detailRes, historyRes, colValRes, completenessRes] = await Promise.all([
        companyApi.getById(id),
        ewsApi.getCompanyHistory(id),
        companyApi.getCollateralValuation(id),
        ewsAdvancedApi.getCompleteness(id),
      ]);
      setCompanyDetail(detailRes.data);
      setEwsHistory(historyRes.data || []);
      setCollateralValuation(colValRes.data || []);
      setCompleteness(completenessRes.data || null);
    } catch (err) {
      console.error(err);
    } finally {
      setDetailLoading(false);
    }
  };

  const loadAdvancedData = async (id: string) => {
    if (advancedLoaded) return;
    setAdvancedLoading(true);
    try {
      const [eventsRes, newsRes, marketRes, scRes] = await Promise.all([
        ewsAdvancedApi.getPublicEvents(id),
        ewsAdvancedApi.getNews(id),
        ewsAdvancedApi.getMarketSignal(id),
        ewsAdvancedApi.getSupplyChain(id),
      ]);
      setPublicEvents(eventsRes.data || []);
      setNewsData(newsRes.data || []);
      setMarketSignal(marketRes.data || { listed: false, data: [] });
      setSupplyChain(scRes.data || []);
      setAdvancedLoaded(true);
    } catch (err) {
      console.error(err);
    } finally {
      setAdvancedLoading(false);
    }
  };

  const toggleCollateralHistory = async (collateralId: string) => {
    if (expandedCollateral === collateralId) {
      setExpandedCollateral(null);
      return;
    }
    setExpandedCollateral(collateralId);
    if (!collateralHistory[collateralId] && selectedId) {
      try {
        const res = await companyApi.getCollateralHistory(selectedId, collateralId);
        setCollateralHistory(prev => ({ ...prev, [collateralId]: res.data }));
      } catch {
        setCollateralHistory(prev => ({ ...prev, [collateralId]: null }));
      }
    }
  };

  const profile = companyDetail?.profile;
  const facilities = companyDetail?.facilities || [];
  const collaterals = companyDetail?.collaterals || [];
  const assetClassTrend = companyDetail?.asset_class_trend || [];
  const eclTrend = companyDetail?.ecl_trend || [];
  const ratings = companyDetail?.credit_ratings || [];
  const covenants = companyDetail?.covenants || [];
  const workoutHistory = companyDetail?.workout_history || [];
  const transactionBehavior = companyDetail?.transaction_behavior || [];

  // 담보 이력: collateral_id별 그룹화 (차트용)
  const colValByCollateral: Record<string, any[]> = {};
  for (const cv of collateralValuation) {
    if (!colValByCollateral[cv.collateral_id]) colValByCollateral[cv.collateral_id] = [];
    colValByCollateral[cv.collateral_id].push(cv);
  }
  // 담보 차트 데이터: 분기별 합산 (여러 담보)
  const colValQuarters = [...new Set(collateralValuation.map((cv: any) => cv.valuation_ym))].sort();
  const colValChartData = colValQuarters.map((ym: any) => {
    const entry: any = { label: `${String(ym).slice(0,4)}-Q${Math.ceil(parseInt(String(ym).slice(4)) / 3)}` };
    Object.keys(colValByCollateral).forEach((cid) => {
      const rec = colValByCollateral[cid].find((x: any) => x.valuation_ym === ym);
      if (rec) entry[cid] = rec.appraised_value_억;
    });
    return entry;
  });

  const ewsScoreData = ewsHistory.map((h: any) => ({
    label: formatYm(h.ym),
    ews_score: h.ews_score,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">기업 상세 조회</h1>
        <p className="text-sm text-gray-500 mt-1">기업명 검색 후 상세 정보 확인</p>
      </div>

      {/* 검색 영역 */}
      <Card>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="기업명 입력 시 전체 목록 표시..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              onFocus={() => { setSearchFocused(true); if (!searchResults.length) handleSearch(searchQuery); }}
              onBlur={() => setTimeout(() => setSearchFocused(false), 200)}
              className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>
          {/* 지역 필터 */}
          <div className="flex items-center gap-0.5 border border-gray-200 rounded-lg px-1.5 bg-white">
            <MapPin size={13} className="text-gray-400 mr-0.5" />
            {[{v:'',l:'전체'},{v:'수도권',l:'수도권'},{v:'대구경북',l:'대구경북'},{v:'부산경남',l:'부산경남'}].map(r => (
              <button
                key={r.v}
                onClick={() => handleRegionChange(r.v)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  searchRegion === r.v ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {r.l}
              </button>
            ))}
          </div>
        </div>

        {(searchFocused || searchResults.length > 0) && searchResults.length > 0 && (
          <div className="mt-2 border border-gray-200 rounded-lg overflow-hidden max-h-64 overflow-y-auto">
            {searchResults.map((c) => (
              <button
                key={c.borrower_id}
                onMouseDown={() => {
                  setSelectedId(c.borrower_id);
                  setSearchResults([]);
                  setSearchQuery('');
                  setSearchFocused(false);
                }}
                className={`w-full flex items-center justify-between px-4 py-2 text-sm hover:bg-blue-50 border-b border-gray-100 last:border-0 ${
                  selectedId === c.borrower_id ? 'bg-blue-50' : ''
                }`}
              >
                <span className="font-medium">{c.company_name}</span>
                <span className="text-gray-400 text-xs flex items-center gap-2">
                  {c.region && <span className="flex items-center gap-0.5 text-blue-500"><MapPin size={10}/>{c.region}</span>}
                  {c.firm_size_cd} | {c.industry_cd}
                </span>
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* 기업 상세 */}
      {selectedId && (
        <>
          {detailLoading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : profile ? (
            <>
              {/* 프로필 카드 */}
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">{profile.company_name}</h2>
                    <div className="flex flex-wrap gap-3 mt-2">
                      <span className="text-sm text-gray-500">규모: <strong>{profile.firm_size_cd}</strong></span>
                      <span className="text-sm text-gray-500">업종: <strong>{profile.industry_cd}</strong></span>
                      <span className="text-sm text-gray-500">상장: <strong>{profile.listed_flag ? 'Y' : 'N'}</strong></span>
                      <span className="text-sm text-gray-500">시나리오: <strong>{profile.scenario}</strong></span>
                      {profile.default_ym && (
                        <span className="text-sm text-red-600">부도월: <strong>{formatYm(profile.default_ym)}</strong></span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getEWSGradeBgClass(ewsHistory.length > 0 ? ewsHistory[ewsHistory.length - 1]?.ews_grade : '')}`}>
                      EWS {ewsHistory.length > 0 ? ewsHistory[ewsHistory.length - 1]?.ews_grade : '-'}
                    </span>
                    <p className="text-xs text-gray-500 mt-1">
                      점수: {ewsHistory.length > 0 ? ewsHistory[ewsHistory.length - 1]?.ews_score?.toFixed(1) : '-'}
                    </p>
                    {completeness && (
                      <div className="mt-2 flex flex-col items-end gap-1">
                        <span className={`px-2 py-0.5 text-xs font-semibold rounded ${completeness.tier_color}`}>
                          {completeness.tier_label}
                        </span>
                        <p className="text-xs text-gray-400">
                          완성도 {completeness.data_completeness_pct}% | 신뢰 {completeness.confidence_adj_score?.toFixed(1)}점
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* EWS Score 추이 차트 */}
              <Card title="EWS 점수 추이">
                <TrendChart
                  data={ewsScoreData}
                  xAxisKey="label"
                  lines={[{ key: 'ews_score', name: 'EWS 점수', color: '#e74c3c' }]}
                  height={220}
                  showLegend={false}
                  referenceLines={[
                    { y: 25, label: 'D등급', color: '#dc2626' },
                    { y: 50, label: 'C등급', color: '#e67e22' },
                  ]}
                />
              </Card>

              {/* 탭 */}
              <div>
                <div className="flex gap-1 border-b border-gray-200">
                  {TABS.map((tab, idx) => (
                    <button
                      key={tab}
                      onClick={() => {
                        setActiveTab(idx);
                        if (idx === 9 && selectedId && !advancedLoaded) loadAdvancedData(selectedId);
                      }}
                      className={`px-4 py-2 text-sm font-medium transition-colors ${
                        activeTab === idx
                          ? 'text-blue-700 border-b-2 border-blue-700'
                          : 'text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      {tab}
                    </button>
                  ))}
                </div>

                <div className="mt-4">
                  {/* EWS 신호 탭 */}
                  {activeTab === 0 && (
                    <Card noPadding>
                      <Table
                        columns={[
                          { key: 'ym', header: '기준월', width: '80px', render: (v) => formatYm(v) },
                          { key: 'ews_grade', header: '등급', width: '60px', align: 'center', render: (v) => <span className={`px-1.5 py-0.5 rounded text-xs font-semibold ${getEWSGradeBgClass(v)}`}>{v}</span> },
                          { key: 'ews_score', header: 'EWS점수', width: '80px', align: 'right', render: (v: number) => v?.toFixed(1) },
                          { key: 'ifrs9_stage', header: 'Stage', width: '60px', align: 'center' },
                          { key: 'principal_past_due_days', header: '연체일', width: '70px', align: 'right' },
                          { key: 'debt_to_equity_ratio', header: '부채비율', width: '80px', align: 'right', render: (v: number) => v?.toFixed(1) },
                          { key: 'current_ratio', header: '유동비율', width: '80px', align: 'right', render: (v: number) => v?.toFixed(1) },
                          { key: 'dscr_ratio', header: 'DSCR', width: '70px', align: 'right', render: (v: number) => v?.toFixed(2) },
                          { key: 'limit_utilization_ratio', header: '한도사용률', width: '90px', align: 'right', render: (v: number) => v != null ? `${(v * 100).toFixed(1)}%` : '-' },
                          { key: 'seizure_flag', header: '압류', width: '50px', align: 'center', render: (v: number) => v ? '✓' : '-' },
                        ]}
                        data={[...ewsHistory].reverse()}
                        emptyMessage="EWS 신호 데이터가 없습니다"
                      />
                    </Card>
                  )}

                  {/* 여신 현황 탭 */}
                  {activeTab === 1 && (
                    <Card noPadding>
                      <Table
                        columns={[
                          { key: 'facility_id', header: '여신ID', width: '100px' },
                          { key: 'facility_type', header: '여신유형', width: '100px' },
                          { key: 'committed_amount_억', header: '약정(억)', width: '80px', align: 'right', render: (v: number) => v?.toFixed(1) },
                          { key: 'outstanding_amount_억', header: '잔액(억)', width: '80px', align: 'right', render: (v: number) => v?.toFixed(1) },
                          { key: 'interest_rate', header: '금리', width: '70px', align: 'right', render: (v: number) => `${(v * 100).toFixed(2)}%` },
                          { key: 'maturity_ym', header: '만기', width: '80px', align: 'center', render: (v) => formatYm(v) },
                          { key: 'collateral_type', header: '담보유형', width: '100px' },
                        ]}
                        data={facilities}
                        emptyMessage="여신 데이터가 없습니다"
                      />
                    </Card>
                  )}

                  {/* 자산건전성 탭 */}
                  {activeTab === 2 && (
                    <Card noPadding>
                      <Table
                        columns={[
                          { key: 'ym', header: '기준월', width: '80px', render: (v) => formatYm(v) },
                          {
                            key: 'classification', header: '분류', width: '120px',
                            render: (v: string) => (
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                v === 'NORMAL' ? 'bg-green-100 text-green-800' :
                                v === 'PRECAUTIONARY' ? 'bg-yellow-100 text-yellow-800' :
                                v === 'SUBSTANDARD' ? 'bg-orange-100 text-orange-800' :
                                v === 'DOUBTFUL' ? 'bg-red-100 text-red-800' :
                                'bg-red-200 text-red-900'
                              }`}>{getClassificationLabel(v)}</span>
                            )
                          },
                          { key: 'ews_score', header: 'EWS점수', width: '80px', align: 'right', render: (v: number) => v?.toFixed(1) },
                        ]}
                        data={assetClassTrend}
                        emptyMessage="자산건전성 데이터가 없습니다"
                      />
                    </Card>
                  )}

                  {/* 담보 이력 탭 */}
                  {activeTab === 3 && (
                    <div className="space-y-4">
                      {/* 요약 stats */}
                      {collaterals.length > 0 && (() => {
                        const totalAppraised = collaterals.reduce((s: number, c: any) => s + (c.appraised_value_억 || 0), 0);
                        const totalRecognized = collaterals.reduce((s: number, c: any) => s + (c.recognized_value_억 || 0), 0);
                        const totalPriorLien = collaterals.reduce((s: number, c: any) => s + (c.prior_lien_amount_억 || 0), 0);
                        const avgLtv = collaterals.reduce((s: number, c: any) => s + (c.ltv_pct || 0), 0) / collaterals.length;
                        return (
                          <div className="grid grid-cols-4 gap-3">
                            <div className="p-3 bg-blue-50 rounded-lg border border-blue-200 text-center">
                              <p className="text-xs text-blue-600">담보 건수</p>
                              <p className="text-xl font-bold text-blue-700">{collaterals.length}건</p>
                            </div>
                            <div className="p-3 bg-green-50 rounded-lg border border-green-200 text-center">
                              <p className="text-xs text-green-600">총 평가액</p>
                              <p className="text-xl font-bold text-green-700">{totalAppraised.toFixed(1)}억</p>
                            </div>
                            <div className="p-3 bg-purple-50 rounded-lg border border-purple-200 text-center">
                              <p className="text-xs text-purple-600">총 인정가액</p>
                              <p className="text-xl font-bold text-purple-700">{totalRecognized.toFixed(1)}억</p>
                            </div>
                            <div className={`p-3 rounded-lg border text-center ${avgLtv >= 80 ? 'bg-red-50 border-red-200' : avgLtv >= 60 ? 'bg-yellow-50 border-yellow-200' : 'bg-gray-50 border-gray-200'}`}>
                              <p className={`text-xs ${avgLtv >= 80 ? 'text-red-600' : avgLtv >= 60 ? 'text-yellow-600' : 'text-gray-600'}`}>평균 LTV</p>
                              <p className={`text-xl font-bold ${avgLtv >= 80 ? 'text-red-700' : avgLtv >= 60 ? 'text-yellow-700' : 'text-gray-700'}`}>{avgLtv.toFixed(1)}%</p>
                            </div>
                          </div>
                        );
                      })()}

                      {/* 담보 목록 */}
                      {collaterals.length === 0 ? (
                        <div className="text-center py-12 text-gray-400">담보 데이터가 없습니다</div>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                            <thead>
                              <tr className="bg-gray-50 border-b border-gray-200">
                                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 w-8"></th>
                                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">유형</th>
                                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">세부유형</th>
                                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">소재지/정보</th>
                                <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600">평가액(억)</th>
                                <th className="px-3 py-2 text-center text-xs font-semibold text-gray-600">인정비율</th>
                                <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600">인정가액(억)</th>
                                <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600">선순위(억)</th>
                                <th className="px-3 py-2 text-center text-xs font-semibold text-gray-600">LTV</th>
                                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">감정기관</th>
                                <th className="px-3 py-2 text-center text-xs font-semibold text-gray-600">이력</th>
                              </tr>
                            </thead>
                            <tbody>
                              {collaterals.map((col: any) => (
                                <React.Fragment key={col.collateral_id}>
                                  <tr
                                    className={`border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${expandedCollateral === col.collateral_id ? 'bg-blue-50' : ''}`}
                                    onClick={() => toggleCollateralHistory(col.collateral_id)}
                                  >
                                    <td className="px-3 py-2 text-gray-400">
                                      {expandedCollateral === col.collateral_id
                                        ? <ChevronDown size={14} />
                                        : <ChevronRight size={14} />}
                                    </td>
                                    <td className="px-3 py-2">
                                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                                        col.collateral_type === '부동산' ? 'bg-blue-100 text-blue-700' :
                                        col.collateral_type === '기계' ? 'bg-orange-100 text-orange-700' :
                                        'bg-green-100 text-green-700'
                                      }`}>
                                        {col.collateral_type === '부동산' ? <Building2 size={10} /> :
                                         col.collateral_type === '기계' ? <Cog size={10} /> :
                                         <Package size={10} />}
                                        {col.collateral_type}
                                      </span>
                                    </td>
                                    <td className="px-3 py-2 text-gray-700 text-xs">{col.collateral_subtype || '-'}</td>
                                    <td className="px-3 py-2 text-gray-500 text-xs">
                                      {col.address
                                        ? <>{col.address}{col.area_m2 ? <span className="ml-1 text-gray-400">{col.area_m2.toFixed(0)}㎡</span> : null}</>
                                        : '-'}
                                    </td>
                                    <td className="px-3 py-2 text-right font-mono text-xs">{col.appraised_value_억?.toFixed(1)}</td>
                                    <td className="px-3 py-2 text-center text-xs">{col.recognition_ratio != null ? `${(col.recognition_ratio * 100).toFixed(0)}%` : '-'}</td>
                                    <td className="px-3 py-2 text-right font-mono text-xs">{col.recognized_value_억?.toFixed(1)}</td>
                                    <td className="px-3 py-2 text-right font-mono text-xs text-gray-500">{col.prior_lien_amount_억?.toFixed(1)}</td>
                                    <td className="px-3 py-2 text-center">
                                      <span className={`px-1.5 py-0.5 rounded text-xs font-semibold ${
                                        (col.ltv_pct || 0) >= 80 ? 'bg-red-100 text-red-700' :
                                        (col.ltv_pct || 0) >= 60 ? 'bg-yellow-100 text-yellow-700' :
                                        'bg-green-100 text-green-700'
                                      }`}>{col.ltv_pct?.toFixed(1)}%</span>
                                    </td>
                                    <td className="px-3 py-2 text-gray-500 text-xs">{col.appraiser || '-'}</td>
                                    <td className="px-3 py-2 text-center">
                                      <TrendingUp size={14} className="inline text-blue-400" />
                                    </td>
                                  </tr>
                                  {/* 평가 이력 확장 패널 */}
                                  {expandedCollateral === col.collateral_id && (
                                    <tr>
                                      <td colSpan={11} className="bg-blue-50 px-6 py-4">
                                        {!collateralHistory[col.collateral_id] ? (
                                          <div className="flex items-center gap-2 text-sm text-gray-500">
                                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                                            이력 로딩중...
                                          </div>
                                        ) : (collateralHistory[col.collateral_id]?.history || []).length === 0 ? (
                                          <p className="text-sm text-gray-500">평가 이력이 없습니다.</p>
                                        ) : (
                                          <div>
                                            <h4 className="text-xs font-semibold text-blue-700 mb-2">
                                              분기별 평가 이력 — {col.collateral_id}
                                              {col.address ? ` (${col.address})` : ''}
                                            </h4>
                                            <table className="w-full text-xs">
                                              <thead>
                                                <tr className="border-b border-blue-200 text-gray-500">
                                                  <th className="px-2 py-1 text-left">기준분기</th>
                                                  <th className="px-2 py-1 text-left">평가방법</th>
                                                  <th className="px-2 py-1 text-right">이전 평가액</th>
                                                  <th className="px-2 py-1 text-right">평가액(억)</th>
                                                  <th className="px-2 py-1 text-right">시장가(억)</th>
                                                  <th className="px-2 py-1 text-center">전분기대비</th>
                                                  <th className="px-2 py-1 text-center">LTV</th>
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {(collateralHistory[col.collateral_id]?.history || []).map((v: any) => (
                                                  <tr key={v.valuation_id} className="border-b border-blue-100 hover:bg-blue-100">
                                                    <td className="px-2 py-1 text-gray-700">{v.label}</td>
                                                    <td className="px-2 py-1 text-gray-500">{v.valuation_method}</td>
                                                    <td className="px-2 py-1 text-right text-gray-400 font-mono">
                                                      {v.previous_value_억 != null ? v.previous_value_억.toFixed(2) : '-'}
                                                    </td>
                                                    <td className="px-2 py-1 text-right font-mono font-semibold text-gray-800">{v.appraised_value_억?.toFixed(2)}</td>
                                                    <td className="px-2 py-1 text-right font-mono text-gray-600">{v.market_value_억?.toFixed(2)}</td>
                                                    <td className={`px-2 py-1 text-center font-semibold ${
                                                      (v.change_pct || 0) > 0 ? 'text-green-600' :
                                                      (v.change_pct || 0) < 0 ? 'text-red-600' : 'text-gray-400'
                                                    }`}>
                                                      {v.change_pct > 0 ? '+' : ''}{v.change_pct?.toFixed(1)}%
                                                    </td>
                                                    <td className="px-2 py-1 text-center">
                                                      <span className={`px-1.5 py-0.5 rounded ${
                                                        (v.ltv_pct || 0) >= 80 ? 'bg-red-100 text-red-700' :
                                                        (v.ltv_pct || 0) >= 60 ? 'bg-yellow-100 text-yellow-700' :
                                                        'bg-green-100 text-green-700'
                                                      }`}>{v.ltv_pct?.toFixed(1)}%</span>
                                                    </td>
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          </div>
                                        )}
                                      </td>
                                    </tr>
                                  )}
                                </React.Fragment>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ECL 탭 */}
                  {activeTab === 4 && (
                    <Card noPadding>
                      <Table
                        columns={[
                          { key: 'ym', header: '기준월', width: '80px', render: (v) => formatYm(v) },
                          { key: 'stage', header: 'Stage', width: '70px', align: 'center', render: (v: number) => (
                            <span className={`px-1.5 py-0.5 rounded text-xs font-semibold ${
                              v === 1 ? 'bg-green-100 text-green-800' :
                              v === 2 ? 'bg-yellow-100 text-yellow-800' :
                              'bg-red-100 text-red-800'
                            }`}>
                              {v === 1 ? '정상 (S1)' : v === 2 ? '요주의 (S2)' : '고정이하 (S3)'}
                            </span>
                          )},
                          { key: 'ecl_amount_억', header: 'ECL(억)', width: '80px', align: 'right', render: (v: number) => v?.toFixed(3) },
                          { key: 'ead_억', header: 'EAD(억)', width: '80px', align: 'right', render: (v: number) => v?.toFixed(1) },
                          { key: 'pd_value', header: 'PD', width: '70px', align: 'right', render: (v: number) => `${(v * 100).toFixed(2)}%` },
                          { key: 'lgd', header: 'LGD', width: '70px', align: 'right', render: (v: number) => `${(v * 100).toFixed(1)}%` },
                        ]}
                        data={eclTrend}
                        emptyMessage="ECL 데이터가 없습니다"
                      />
                    </Card>
                  )}

                  {/* 신용등급 탭 */}
                  {activeTab === 5 && (
                    <Card noPadding>
                      <Table
                        columns={[
                          { key: 'rating_ym', header: '평가월', width: '100px', render: (v) => formatYm(v) },
                          { key: 'grade', header: '신용등급', width: '100px', align: 'center', render: (v: string) => <span className="font-semibold text-blue-700">{v}</span> },
                        ]}
                        data={ratings}
                        emptyMessage="신용등급 데이터가 없습니다"
                      />
                    </Card>
                  )}

                  {/* 코베넌트 탭 */}
                  {activeTab === 6 && (
                    <Card noPadding>
                      <Table
                        columns={[
                          { key: 'check_ym', header: '점검월', width: '80px', render: (v) => formatYm(v) },
                          { key: 'covenant_type', header: '코베넌트 유형', width: '100px' },
                          {
                            key: 'result', header: '결과', width: '80px', align: 'center',
                            render: (v: string) => (
                              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColorClass(v)}`}>{v}</span>
                            )
                          },
                          { key: 'actual_value', header: '실제값', width: '80px', align: 'right', render: (v: number) => v?.toFixed(3) },
                          { key: 'threshold_value', header: '기준값', width: '80px', align: 'right', render: (v: number) => v?.toFixed(3) },
                        ]}
                        data={covenants}
                        emptyMessage="코베넌트 데이터가 없습니다"
                      />
                    </Card>
                  )}

                  {/* 거래행태 탭 */}
                  {activeTab === 7 && (
                    <div className="space-y-4">
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <Card title="예금잔액 / 입출금비율 추이">
                          <TrendChart
                            data={transactionBehavior.map((h: any) => ({
                              label: formatYm(h.ym),
                              avg_deposit_balance_억: h.avg_deposit_balance_억,
                              inflow_outflow_ratio: h.inflow_outflow_ratio,
                            }))}
                            xAxisKey="label"
                            lines={[
                              { key: 'avg_deposit_balance_억', name: '예금잔액(억)', color: '#3b82f6' },
                              { key: 'inflow_outflow_ratio', name: '입출금비율', color: '#10b981' },
                            ]}
                            height={220}
                          />
                        </Card>
                        <Card title="한도사용률 / 연체일수 추이">
                          <TrendChart
                            data={transactionBehavior.map((h: any) => ({
                              label: formatYm(h.ym),
                              limit_utilization_pct: h.limit_utilization_ratio * 100,
                              principal_past_due_days: h.principal_past_due_days,
                            }))}
                            xAxisKey="label"
                            lines={[
                              { key: 'limit_utilization_pct', name: '한도사용률(%)', color: '#f59e0b' },
                              { key: 'principal_past_due_days', name: '연체일수', color: '#ef4444' },
                            ]}
                            height={220}
                          />
                        </Card>
                      </div>
                      <Card noPadding>
                        <Table
                          columns={[
                            { key: 'ym', header: '기준월', width: '80px', render: (v) => formatYm(v) },
                            { key: 'avg_deposit_balance_억', header: '예금잔액(억)', width: '100px', align: 'right', render: (v: number) => v?.toFixed(2) },
                            { key: 'inflow_outflow_ratio', header: '입출금비율', width: '100px', align: 'right', render: (v: number) => v?.toFixed(3) },
                            { key: 'limit_utilization_ratio', header: '한도사용률', width: '100px', align: 'right', render: (v: number) => `${(v * 100).toFixed(1)}%` },
                            { key: 'principal_past_due_days', header: '연체일수', width: '80px', align: 'right' },
                          ]}
                          data={transactionBehavior}
                          emptyMessage="거래행태 데이터가 없습니다"
                        />
                      </Card>
                    </div>
                  )}

                  {/* 선행 신호 탭 */}
                  {activeTab === 9 && (
                    <div className="space-y-6">
                      {advancedLoading ? (
                        <div className="flex items-center justify-center h-40">
                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                        </div>
                      ) : (
                        <>
                          {/* 데이터 완성도 프로파일 */}
                          {completeness && (
                            <Card title="데이터 완성도 프로파일">
                              <div className="flex items-center gap-4 mb-4">
                                <span className={`px-3 py-1 text-sm font-bold rounded ${completeness.tier_color}`}>
                                  {completeness.tier_label}
                                </span>
                                <div className="flex-1">
                                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                                    <span>전체 완성도</span>
                                    <span>{completeness.data_completeness_pct}%</span>
                                  </div>
                                  <div className="w-full bg-gray-200 rounded-full h-2">
                                    <div
                                      className="h-2 rounded-full bg-blue-500"
                                      style={{ width: `${completeness.data_completeness_pct}%` }}
                                    />
                                  </div>
                                </div>
                                <div className="text-right">
                                  <p className="text-xs text-gray-500">신뢰 조정 점수</p>
                                  <p className="text-lg font-bold text-gray-800">{completeness.confidence_adj_score?.toFixed(1)}</p>
                                  <p className="text-xs text-gray-400">원점수: {completeness.raw_ews_score?.toFixed(1)}</p>
                                </div>
                              </div>
                              <div className="grid grid-cols-3 gap-2">
                                {(completeness.feature_groups || []).map((fg: any) => (
                                  <div key={fg.name} className={`flex items-center justify-between px-3 py-2 rounded-lg border ${
                                    fg.available ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'
                                  }`}>
                                    <div className="flex items-center gap-2">
                                      <span className={`w-2 h-2 rounded-full ${fg.available ? 'bg-green-500' : 'bg-gray-300'}`} />
                                      <span className={`text-xs font-medium ${fg.available ? 'text-green-800' : 'text-gray-400'}`}>{fg.name}</span>
                                    </div>
                                    <span className="text-xs text-gray-400">가중 {fg.weight}%</span>
                                  </div>
                                ))}
                              </div>
                            </Card>
                          )}

                          {/* 공공 이벤트 타임라인 */}
                          <Card title="공공 이벤트 타임라인">
                            {publicEvents.length === 0 ? (
                              <p className="text-sm text-gray-400 text-center py-6">공공 이벤트 없음</p>
                            ) : (
                              <div className="space-y-2">
                                {publicEvents.map((ev: any) => (
                                  <div key={ev.event_id} className="flex items-start gap-3 p-3 rounded-lg border border-gray-100 hover:bg-gray-50">
                                    <span className={`px-2 py-0.5 text-xs font-semibold rounded whitespace-nowrap ${ev.severity_style}`}>
                                      {ev.severity}
                                    </span>
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <span className="text-sm font-medium text-gray-800">{ev.event_label}</span>
                                        <span className="text-xs text-gray-400">{formatYm(ev.event_ym)}</span>
                                        {ev.resolved_flag ? (
                                          <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs rounded">해소</span>
                                        ) : (
                                          <span className="px-1.5 py-0.5 bg-red-100 text-red-700 text-xs rounded">진행중</span>
                                        )}
                                      </div>
                                      <p className="text-xs text-gray-500 mt-0.5 truncate">{ev.description}</p>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </Card>

                          {/* 뉴스 감성 추이 */}
                          <Card title="뉴스 감성 월별 추이">
                            {newsData.length === 0 ? (
                              <p className="text-sm text-gray-400 text-center py-6">뉴스 데이터 없음</p>
                            ) : (
                              <TrendChart
                                data={newsData.map((n: any) => ({
                                  label: formatYm(n.ym),
                                  긍정: n.positive_count,
                                  부정: n.negative_count,
                                  감성점수: Math.round(n.avg_sentiment_score * 100),
                                }))}
                                xAxisKey="label"
                                lines={[
                                  { key: '긍정', name: '긍정 기사', color: '#10b981' },
                                  { key: '부정', name: '부정 기사', color: '#ef4444' },
                                  { key: '감성점수', name: '감성점수(×100)', color: '#6366f1' },
                                ]}
                                height={220}
                              />
                            )}
                          </Card>

                          {/* 시장 신호 (상장사만) */}
                          {marketSignal.listed ? (
                            <Card title="시장 신호 (상장사)">
                              <TrendChart
                                data={marketSignal.data.map((m: any) => ({
                                  label: formatYm(m.ym),
                                  주가변동률: m.stock_price_change_pct,
                                  CDS스프레드: m.cds_spread_bps,
                                  공매도비율: m.short_interest_ratio * 100,
                                }))}
                                xAxisKey="label"
                                lines={[
                                  { key: '주가변동률', name: '주가변동(%)', color: '#3b82f6' },
                                  { key: 'CDS스프레드', name: 'CDS스프레드(bps)', color: '#f59e0b' },
                                  { key: '공매도비율', name: '공매도비율(%)', color: '#ef4444' },
                                ]}
                                height={220}
                              />
                            </Card>
                          ) : (
                            <Card title="시장 신호">
                              <p className="text-sm text-gray-400 text-center py-6">비상장 기업 — 시장 신호 없음</p>
                            </Card>
                          )}

                          {/* 공급망 위험 */}
                          <Card title="공급망 위험 관계">
                            {supplyChain.length === 0 ? (
                              <p className="text-sm text-gray-400 text-center py-6">공급망 데이터 없음</p>
                            ) : (
                              <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="bg-gray-50 border-b border-gray-200 text-xs text-gray-500">
                                      <th className="px-3 py-2 text-left">거래처명</th>
                                      <th className="px-3 py-2 text-left">관계</th>
                                      <th className="px-3 py-2 text-right">노출비율</th>
                                      <th className="px-3 py-2 text-center">전이위험점수</th>
                                      <th className="px-3 py-2 text-center">거래처 EWS등급</th>
                                      <th className="px-3 py-2 text-center">내부거래처</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-gray-100">
                                    {supplyChain.map((sc: any) => (
                                      <tr key={sc.relation_id} className="hover:bg-gray-50">
                                        <td className="px-3 py-2 font-medium text-gray-800">{sc.counterparty_name}</td>
                                        <td className="px-3 py-2 text-gray-600">{sc.relation_label}</td>
                                        <td className="px-3 py-2 text-right font-mono text-xs">{(sc.exposure_ratio * 100).toFixed(1)}%</td>
                                        <td className="px-3 py-2 text-center">
                                          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                                            sc.contagion_risk_score >= 70 ? 'bg-red-100 text-red-700' :
                                            sc.contagion_risk_score >= 40 ? 'bg-yellow-100 text-yellow-700' :
                                            'bg-green-100 text-green-700'
                                          }`}>{sc.contagion_risk_score}</span>
                                        </td>
                                        <td className="px-3 py-2 text-center">
                                          <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${getEWSGradeBgClass(sc.cp_ews_grade)}`}>
                                            {sc.cp_ews_grade}
                                          </span>
                                        </td>
                                        <td className="px-3 py-2 text-center text-xs text-gray-500">
                                          {sc.is_internal ? '내부' : '-'}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </Card>
                        </>
                      )}
                    </div>
                  )}

                  {/* Workout 이력 탭 */}
                  {activeTab === 8 && (
                    <div className="space-y-4">
                      {workoutHistory.length === 0 ? (
                        <div className="text-center py-12 text-gray-400">Workout 이력이 없습니다</div>
                      ) : (
                        workoutHistory.map((w: any) => (
                          <Card key={w.workout_id} title={`${w.workout_type} (${formatYm(w.workout_start_ym)})`}>
                            <div className="mb-3 flex flex-wrap gap-4 text-sm">
                              <span className="text-gray-500">원금: <strong className="font-mono">{w.original_balance_억?.toFixed(1)}억</strong></span>
                              <span className="text-gray-500">회수율: <strong className={`font-mono ${w.recovery_rate >= 0.5 ? 'text-green-600' : 'text-red-600'}`}>{(w.recovery_rate * 100).toFixed(1)}%</strong></span>
                              <span className="text-gray-500">결과: <strong><span className={`px-1.5 py-0.5 rounded text-xs ${getStatusColorClass(w.outcome)}`}>{w.outcome}</span></strong></span>
                            </div>
                            {w.scenarios && w.scenarios.length > 0 && (
                              <div>
                                <p className="text-xs font-semibold text-gray-500 mb-2">회수 시나리오</p>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                  {w.scenarios.map((s: any) => {
                                    const styleMap: Record<string, string[]> = {
                                      OPTIMISTIC:  ['bg-green-50','text-green-700','border-green-200','낙관적'],
                                      BASE:        ['bg-blue-50','text-blue-700','border-blue-200','기본'],
                                      PESSIMISTIC: ['bg-red-50','text-red-700','border-red-200','비관적'],
                                    };
                                    const [bg, txt, border, label] = styleMap[s.scenario_type] || styleMap.BASE;
                                    return (
                                      <div key={s.scenario_type} className={`${bg} border ${border} rounded p-2 text-sm`}>
                                        <p className={`font-bold ${txt} mb-1`}>{label} ({s.probability_pct}%)</p>
                                        <div className="space-y-0.5 text-xs">
                                          <div className="flex justify-between"><span>회수</span><span className="font-mono">{s.recovery_amount_억?.toFixed(1)}억</span></div>
                                          <div className="flex justify-between"><span>NPV</span><span className="font-mono">{s.npv_억?.toFixed(1)}억</span></div>
                                          <div className="flex justify-between"><span>IRR</span><span className="font-mono">{s.irr_pct?.toFixed(1)}%</span></div>
                                          <div className="flex justify-between"><span>기간</span><span className="font-mono">{s.recovery_timeline_months}개월</span></div>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                                <div className="mt-2 pt-2 border-t border-gray-200 flex justify-between text-sm">
                                  <span className="text-gray-500">가중평균 기대 회수액</span>
                                  <span className="font-bold text-purple-700 font-mono">{w.weighted_expected_recovery_억?.toFixed(2)}억</span>
                                </div>
                              </div>
                            )}
                          </Card>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="text-center py-12 text-gray-500">기업 정보를 불러오지 못했습니다</div>
          )}
        </>
      )}

      {!selectedId && (
        <div className="text-center py-24 text-gray-400">
          <Search size={48} className="mx-auto mb-4 opacity-30" />
          <p className="text-lg">기업명을 검색하여 상세 정보를 확인하세요</p>
        </div>
      )}
    </div>
  );
}

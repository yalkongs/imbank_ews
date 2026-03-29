import axios from 'axios';

// 환경변수가 있으면 Railway URL, 없으면 상대 경로 (로컬/Railway 단독 배포)
const BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 요청 인터셉터
api.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
);

// 응답 인터셉터
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 503) {
      console.warn('DB 초기화 중 (503):', error.response.data?.detail);
    } else {
      console.error('API Error:', error);
    }
    return Promise.reject(error);
  }
);

// Dashboard API
export const dashboardApi = {
  getSummary: () => api.get('/dashboard/summary'),
  getGradeTrend: () => api.get('/dashboard/grade-trend'),
  getEWSAlerts: () => api.get('/dashboard/ews-alerts'),
};

// EWS API
export const ewsApi = {
  getAlerts: (params?: { ym?: number; grade?: string; firm_size?: string; industry?: string; region?: string }) =>
    api.get('/ews/alerts', { params }),
  getGradeDistribution: (ym?: number) =>
    api.get('/ews/grade-distribution', { params: ym ? { ym } : undefined }),
  getCompanyHistory: (borrowerId: string) =>
    api.get(`/ews/company/${borrowerId}/history`),
  getCompanyProfile: (borrowerId: string) =>
    api.get(`/ews/company/${borrowerId}/profile`),
};

// Company API
export const companyApi = {
  getList: () => api.get('/company/list'),
  getById: (borrowerId: string) => api.get(`/company/${borrowerId}`),
  search: (q: string, region = '', limit = 500) => api.get('/company/search', { params: { q, region, limit } }),
  getCollateralValuation: (borrowerId: string) => api.get(`/company/${borrowerId}/collateral-valuation`),
  getCollateralHistory: (borrowerId: string, collateralId: string) =>
    api.get(`/company/${borrowerId}/collateral/${collateralId}/valuation`),
};

// Portfolio API
export const portfolioApi = {
  getSummary: () => api.get('/portfolio/summary'),
  getConcentration: () => api.get('/portfolio/concentration'),
  getECLSummary: () => api.get('/portfolio/ecl-summary'),
};

// Asset Classification API
export const assetClassificationApi = {
  getDistribution: (ym?: number) =>
    api.get('/asset-classification/distribution', { params: ym ? { ym } : undefined }),
  getTrend: () => api.get('/asset-classification/trend'),
  getList: () => api.get('/asset-classification/list'),
};

// ECL API
export const eclApi = {
  getSummary: () => api.get('/ecl/summary'),
  getTrend: () => api.get('/ecl/trend'),
  getByGrade: () => api.get('/ecl/by-grade'),
  getByStageTrend: () => api.get('/ecl/by-stage-trend'),
};

// Covenant API
export const covenantApi = {
  getSummary: () => api.get('/covenant/summary'),
  getBreaches: () => api.get('/covenant/breaches'),
  getTrend: () => api.get('/covenant/trend'),
};

// Workout API
export const workoutApi = {
  getSummary: () => api.get('/workout/summary'),
  getList: () => api.get('/workout/list'),
  getRecoveryTrend: () => api.get('/workout/recovery-trend'),
  getScenarios: (workoutId: string) => api.get(`/workout/scenarios/${workoutId}`),
  getScenarioSummary: () => api.get('/workout/scenario-summary'),
};

// Model Performance API
export const modelPerfApi = {
  getSummary: () => api.get('/model-perf/summary'),
  getConfusion: () => api.get('/model-perf/confusion'),
  getLeadTime: () => api.get('/model-perf/lead-time'),
  getTierModels: () => api.get('/model-perf/tier-models'),
  retrain: (tier: string, password: string) =>
    api.post('/model-perf/retrain', { tier, password }),
};

// EWS Action API
export const ewsActionApi = {
  getSummary: () => api.get('/ews-action/summary'),
  getList: (params?: any) => api.get('/ews-action/list', { params }),
  getByCompany: (id: string) => api.get(`/ews-action/by-company/${id}`),
};

// Maturity API
export const maturityApi = {
  getCalendar: (refYm?: number) => api.get('/maturity/calendar', { params: { ref_ym: refYm } }),
  getHeatmap: (refYm?: number) => api.get('/maturity/heatmap', { params: { ref_ym: refYm } }),
  getSummary: (refYm?: number) => api.get('/maturity/summary', { params: { ref_ym: refYm } }),
};

// Monthly Report API
export const monthlyReportApi = {
  getSummary: (ym?: number) => api.get('/monthly-report/summary', { params: { ym } }),
  getGradeChange: (ym?: number) => api.get('/monthly-report/grade-change', { params: { ym } }),
  getTrend: () => api.get('/monthly-report/trend'),
};

// Migration API
export const migrationApi = {
  getMatrix: (fromYm: number, toYm: number) =>
    api.get('/migration/matrix', { params: { from_ym: fromYm, to_ym: toYm } }),
  getTrend: (grade: string) => api.get('/migration/trend', { params: { grade } }),
};

// Benchmark API
export const benchmarkApi = {
  getIndustry: (industryCd: string, ym?: number) =>
    api.get('/benchmark/industry', { params: { industry_cd: industryCd, ym } }),
  getCompany: (borrowerId: string, ym?: number) =>
    api.get(`/benchmark/company/${borrowerId}`, { params: { ym } }),
};

// Stress Test API
export const stressTestApi = {
  getScenarios: () => api.get('/stress-test/scenarios'),
  getImpact: (scenarioId: string) => api.get(`/stress-test/impact/${scenarioId}`),
  getCustom: (params: any) => api.get('/stress-test/custom', { params }),
};

// RM API
export const rmApi = {
  getList: () => api.get('/rm/list'),
  getPortfolio: (rmId: string) => api.get(`/rm/${rmId}/portfolio`),
  getSummary: (rmId: string) => api.get(`/rm/${rmId}/summary`),
  getComparison: () => api.get('/rm/comparison'),
};

// Concentration API
export const concentrationApi = {
  getStatus: (ym?: number) => api.get('/concentration/status', { params: { ym } }),
  getTrend: (dimension: string, value: string) =>
    api.get('/concentration/trend', { params: { dimension, dimension_value: value } }),
};

// Search API
export const searchApi = {
  searchCompany: (q: string, region = '', limit = 100, offset = 0) =>
    api.get('/search/company', { params: { q, region, limit, offset } }),
};

// EWS Advanced API
export const ewsAdvancedApi = {
  getTransaction: (borrowerId: string) =>
    api.get(`/ews-advanced/company/${borrowerId}/transaction`),
  getPublicEvents: (borrowerId: string) =>
    api.get(`/ews-advanced/company/${borrowerId}/public-events`),
  getNews: (borrowerId: string) =>
    api.get(`/ews-advanced/company/${borrowerId}/news`),
  getMarketSignal: (borrowerId: string) =>
    api.get(`/ews-advanced/company/${borrowerId}/market-signal`),
  getSupplyChain: (borrowerId: string) =>
    api.get(`/ews-advanced/company/${borrowerId}/supply-chain`),
  getCompleteness: (borrowerId: string) =>
    api.get(`/ews-advanced/company/${borrowerId}/completeness`),
  getAlertSummary: () =>
    api.get('/ews-advanced/alerts/summary'),
};

export default api;


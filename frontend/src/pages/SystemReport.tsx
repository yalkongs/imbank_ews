import React, { useState } from 'react';
import { Printer, ChevronDown, ChevronRight } from 'lucide-react';

/* ─────────────────────────────────────────────
   공통 스타일 상수
───────────────────────────────────────────── */
const H1 = "text-2xl font-bold text-gray-900 mb-1";
const H2 = "text-xl font-bold text-blue-800 mt-10 mb-3 pb-2 border-b-2 border-blue-200 print:mt-8";
const H3 = "text-base font-bold text-gray-800 mt-6 mb-2";
const H4 = "text-sm font-bold text-gray-700 mt-4 mb-1";
const P  = "text-sm text-gray-700 leading-relaxed mb-2";
const UL = "list-disc list-inside text-sm text-gray-700 leading-relaxed space-y-1 mb-3 ml-2";
const OL = "list-decimal list-inside text-sm text-gray-700 leading-relaxed space-y-1 mb-3 ml-2";

/* ─────────────────────────────────────────────
   소형 카드 컴포넌트
───────────────────────────────────────────── */
function InfoCard({ title, children, color = 'blue' }: {
  title: string; children: React.ReactNode; color?: 'blue' | 'green' | 'yellow' | 'red' | 'gray' | 'purple';
}) {
  const colors: Record<string, string> = {
    blue:   'border-blue-200 bg-blue-50',
    green:  'border-green-200 bg-green-50',
    yellow: 'border-yellow-200 bg-yellow-50',
    red:    'border-red-200 bg-red-50',
    gray:   'border-gray-200 bg-gray-50',
    purple: 'border-purple-200 bg-purple-50',
  };
  const titleColors: Record<string, string> = {
    blue:   'text-blue-800',
    green:  'text-green-800',
    yellow: 'text-yellow-800',
    red:    'text-red-800',
    gray:   'text-gray-800',
    purple: 'text-purple-800',
  };
  return (
    <div className={`rounded-lg border p-4 mb-3 ${colors[color]}`}>
      <p className={`text-xs font-bold uppercase tracking-wider mb-2 ${titleColors[color]}`}>{title}</p>
      {children}
    </div>
  );
}

/* ─────────────────────────────────────────────
   접을 수 있는 섹션
───────────────────────────────────────────── */
function Collapsible({ title, children, defaultOpen = false }: {
  title: string; children: React.ReactNode; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-gray-200 rounded-lg mb-4 print:border-0 print:block">
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-gray-700 hover:bg-gray-50 rounded-lg print:hidden"
        onClick={() => setOpen(!open)}
      >
        <span>{title}</span>
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>
      <div className={`px-4 pb-4 ${open ? 'block' : 'hidden'} print:block print:px-0`}>
        {children}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   테이블 컴포넌트
───────────────────────────────────────────── */
function ReportTable({ headers, rows }: { headers: string[]; rows: (string | React.ReactNode)[][] }) {
  return (
    <div className="overflow-x-auto mb-4">
      <table className="w-full text-xs border border-gray-200 rounded-lg overflow-hidden">
        <thead>
          <tr className="bg-gray-100">
            {headers.map((h, i) => (
              <th key={i} className="px-3 py-2 text-left font-semibold text-gray-600 border-b border-gray-200">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className={ri % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-2 text-gray-700 border-b border-gray-100">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ─────────────────────────────────────────────
   배지
───────────────────────────────────────────── */
function Badge({ label, color }: { label: string; color: string }) {
  return <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold mr-1 ${color}`}>{label}</span>;
}

/* ═══════════════════════════════════════════════════════════
   메인 보고서 컴포넌트
═══════════════════════════════════════════════════════════ */
export default function SystemReport() {
  const handlePrint = () => window.print();

  return (
    <>
      {/* 인쇄 전용 CSS */}
      <style>{`
        @media print {
          body { font-size: 11pt; }
          .no-print { display: none !important; }
          .print-break { page-break-before: always; }
          h2 { page-break-after: avoid; }
          table { page-break-inside: avoid; }
        }
      `}</style>

      <div className="max-w-5xl mx-auto pb-16">

        {/* ── 헤더 ── */}
        <div className="flex items-start justify-between mb-6 no-print">
          <div>
            <h1 className={H1}>iM뱅크 기업여신 EWS 시스템 종합 보고서</h1>
            <p className="text-sm text-gray-500">
              기준일: 2026년 3월
            </p>
            <p className="text-xs text-gray-400 mt-0.5">개발: 황원철</p>
          </div>
          <button
            onClick={handlePrint}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 shrink-0"
          >
            <Printer size={16} />
            PDF로 저장
          </button>
        </div>

        {/* 인쇄용 타이틀 */}
        <div className="hidden print:block mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">iM뱅크 기업여신 EWS 시스템 종합 보고서</h1>
          <p className="text-sm text-gray-500">기준일: 2026년 3월</p>
          <p className="text-xs text-gray-400 mt-0.5">개발: 황원철</p>
          <hr className="mt-4 border-gray-300" />
        </div>

        {/* ────────────────────────────────── */}
        {/* 1. 시스템 개요                     */}
        {/* ────────────────────────────────── */}
        <h2 className={H2}>1. 시스템 개요 및 목적</h2>

        <p className={P}>
          iM뱅크 기업여신 조기경보 시스템(EWS: Early Warning System)은 기업 차주의 신용 위험을 조기에
          탐지하고 선제적인 여신 관리를 가능하게 하는 데이터 기반 리스크 관리 플랫폼입니다. 본 시스템은
          국내 중소기업 여신 포트폴리오의 특수성과 iM뱅크의 지역 기반 영업 특성을 반영하여
          설계되었습니다.
        </p>

        <div className="grid grid-cols-3 gap-3 mb-6">
          {[
            { label: '모니터링 기업 수', value: '20,000개', sub: '대구경북 50% · 부산경남 25% · 수도권 25%', color: 'blue' },
            { label: '데이터 기간', value: '36개월', sub: '2023-01 ~ 2025-12', color: 'green' },
            { label: 'EWS 등급 체계', value: '4단계', sub: 'A(정상) / B(주의) / C(경계) / D(위험)', color: 'yellow' },
          ].map(item => (
            <InfoCard key={item.label} title={item.label} color={item.color as any}>
              <p className="text-2xl font-bold text-gray-900">{item.value}</p>
              <p className="text-xs text-gray-500 mt-1">{item.sub}</p>
            </InfoCard>
          ))}
        </div>

        <h3 className={H3}>1.1 주요 기능 범위</h3>
        <ReportTable
          headers={['기능 영역', '세부 기능', '주요 산출물']}
          rows={[
            ['EWS 경보', '월별 등급 산출, 경보 기업 식별, 액션 관리', 'EWS 등급(A/B/C/D), 경보 리스트'],
            ['여신 포트폴리오', '업종별·규모별 집중도, 만기 도래 관리', '집중도 지표, 만기 캘린더'],
            ['자산건전성', 'IFRS9 Stage 분류, ECL 충당금 산출', 'Stage 분류, PD/LGD/EAD'],
            ['선행지표 고도화', '거래행동, 공공이벤트, 뉴스감성, 시장신호, 공급망', '데이터 완성도 Tier (T1/T2/T3)'],
            ['리스크 분석', '등급 전이 행렬, 스트레스 테스트, 코베넌트', '전이 확률, 시나리오 충격량'],
            ['NPL/Workout', '부실채권 관리, 회수율 분석, 시나리오', '회수 예상액, NPV/IRR'],
            ['모델 성능', 'AUROC, KS 통계, 혼동행렬, 선행시간', '모델 검증 리포트'],
          ]}
        />

        {/* ────────────────────────────────── */}
        {/* 2. 데이터 생성 방법론              */}
        {/* ────────────────────────────────── */}
        <h2 className={H2}>2. 모델 학습용 데이터 생성 방법론</h2>

        <p className={P}>
          본 시스템의 검증용 합성 데이터는 실제 한국 기업 여신 시장의 통계적 특성을 기반으로 합성(Synthetic)
          생성됩니다. 데이터 생성기는 iM뱅크의 실제 영업 지역 분포, 업종 구성비, 부도율 수준을 반영하며,
          향후 실데이터와의 교체를 전제로 설계되었습니다.
        </p>

        <Collapsible title="2.1 기업 모집단 설계 — 지역·업종·규모 배분" defaultOpen>
          <h4 className={H4}>지역 배분 (iM뱅크 영업 특성 반영)</h4>
          <ReportTable
            headers={['지역', '비중', '주요 업종', '특징']}
            rows={[
              ['대구경북', '50%', '섬유(K01A), 자동차부품(K01B), 건설(K02)', '전통 제조업 중심, 중소기업 밀집'],
              ['부산경남', '25%', '도소매(K03), 운수물류(K08), 건설(K02)', '항만·물류 기반, 조선 연관 업종'],
              ['수도권', '25%', '서비스(K04), IT(K05), 도소매(K03)', '대기업·중견기업 비중 높음'],
            ]}
          />
          <h4 className={H4}>기업 규모 배분</h4>
          <ReportTable
            headers={['규모', '비중', '설명', '데이터 Tier']}
            rows={[
              ['대기업', '2%', '총자산 5,000억 이상 또는 매출 1,500억 이상', 'T1 (완성도 75~95%)'],
              ['중견기업', '13%', '총자산 1,000~5,000억', 'T2 (완성도 45~75%)'],
              ['중소기업', '35%', '총자산 120~1,000억', 'T2 (완성도 45~75%)'],
              ['소기업', '50%', '총자산 120억 미만', 'T3 (완성도 15~50%)'],
            ]}
          />
        </Collapsible>

        <Collapsible title="2.2 차주 시나리오 및 부도율 설계">
          <p className={P}>
            데이터셋의 차주는 세 가지 시나리오로 분류되며, 각 시나리오별 월별 EWS 점수 궤적이 다르게
            생성됩니다. 이는 생존 분석(Survival Analysis) 기반의 현실적인 부도 경로 모사를 위한 것입니다.
          </p>
          <ReportTable
            headers={['시나리오', '비중', '설명', '부도율', 'EWS 점수 패턴']}
            rows={[
              ['NORMAL', '80%', '정상 운영 기업', '~3%', '90 이상 유지, 완만한 변동'],
              ['DEFAULT', '12%', '부도 발생 기업', '100%', '점진적 하락 후 D등급 진입'],
              ['RECOVERY', '8%', '부도 후 회생 기업', '회생 완료', '하락 후 반등 패턴'],
            ]}
          />
          <h4 className={H4}>부도 경로 유형 (3가지)</h4>
          <ul className={UL}>
            <li><strong>ACUTE (급성 부도)</strong>: 외부 충격으로 인한 급격한 신용 악화 (3~6개월 내)</li>
            <li><strong>CHRONIC (만성 부도)</strong>: 재무 지표의 점진적 악화 (12~24개월 추세)</li>
            <li><strong>EVENT (이벤트 부도)</strong>: 공공 이벤트(압류, 세금 체납 등) 연계 부도</li>
          </ul>
        </Collapsible>

        <Collapsible title="2.3 월별 신호 데이터 생성 로직">
          <p className={P}>
            각 기업에 대해 36개월(2023-01 ~ 2025-12)의 월별 신호 데이터가 생성됩니다.
            핵심 지표들은 거시경제 국면, 업종 특성, 기업 시나리오를 종합하여 확률적으로 생성됩니다.
          </p>
          <ReportTable
            headers={['지표 카테고리', '주요 변수', '생성 방식']}
            rows={[
              ['재무 지표', '부채비율, 유동비율, DSCR, ROE', '업종 기준 정규분포 + 시나리오별 트렌드'],
              ['연체/부실', '연체일수, Stage, 압류 여부', '부도 경로 함수로 결정론적 생성'],
              ['한도 사용률', '여신 한도 대비 사용액', '월별 베타 분포, 악화기 급등'],
              ['소송/압류', '12개월 소송 건수, 압류 플래그', '이벤트 부도 경로 연계'],
              ['EWS 점수', '0~100점 (낮을수록 위험)', '가중합산 후 Sigmoid 적용'],
              ['데이터 완성도', 'data_completeness_pct', '기업 규모 기반 Beta 분포 샘플링'],
            ]}
          />
          <InfoCard title="EWS 등급 경계값" color="yellow">
            <div className="flex gap-3 flex-wrap text-xs">
              <span><Badge label="A등급" color="bg-green-100 text-green-800" /> EWS 점수 ≥ 75 (정상)</span>
              <span><Badge label="B등급" color="bg-yellow-100 text-yellow-800" /> 50 ≤ 점수 &lt; 75 (주의)</span>
              <span><Badge label="C등급" color="bg-orange-100 text-orange-800" /> 25 ≤ 점수 &lt; 50 (경계)</span>
              <span><Badge label="D등급" color="bg-red-100 text-red-800" /> 점수 &lt; 25 (위험)</span>
            </div>
          </InfoCard>
        </Collapsible>

        <Collapsible title="2.4 선행지표 5종 데이터 구조">
          <ReportTable
            headers={['테이블', '설명', '생성 조건', '주요 컬럼']}
            rows={[
              ['demo_ews_transaction', '월별 거래행동', '전 기업 (36개월)', '일평균잔액, 입출금액, 지연건수, 급여이체, 카드지출변화율'],
              ['demo_ews_public_event', '공공이벤트', 'DEFAULT/RECOVERY 기업 중심', '이벤트 유형, 심각도, 해소 여부, 발생월'],
              ['demo_ews_news_monthly', '뉴스 감성', '전 기업 (데이터 Tier별 커버리지 차등)', '월별 기사수, 긍/부정/중립 건수, 평균감성점수'],
              ['demo_ews_market_signal', '시장신호', '상장사(listed_flag=1)만', '주가변화율, 변동성, CDS스프레드, 공매도비율'],
              ['demo_ews_supply_chain', '공급망 위험', '전 기업의 일부 (관계 네트워크)', '거래처ID, 관계유형, 노출비율, 전이위험점수'],
            ]}
          />
        </Collapsible>

        {/* ────────────────────────────────── */}
        {/* 2-B. 학습 데이터 상세              */}
        {/* ────────────────────────────────── */}
        <h2 className={H2}>2-B. 학습 데이터 규모 및 생성 전략 (상세)</h2>

        <p className={P}>
          EWS 모델은 두 가지 데이터베이스를 기반으로 합니다.
          <strong> 학습용 DB(ews_corporate_v18.db)</strong>는 60,000개 기업 × 108개월(2017-01~2025-12)의
          대규모 합성 데이터로 모델을 훈련하는 데 사용됩니다.
          <strong> 검증용 DB(demo.db)</strong>는 20,000개 기업 × 36개월(2023-01~2025-12)로 구성된
          iM뱅크 특화 운영 시뮬레이션 데이터입니다.
        </p>

        <Collapsible title="2-B.1 학습용 DB — ews_corporate_v24.db" defaultOpen>
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              { label: '기업 수', value: '60,000개', sub: '한국 전체 기업 모집단 모사' },
              { label: '기간', value: '108개월', sub: '2017-01 ~ 2025-12 (9년)' },
              { label: 'ml_feature_label', value: '5,151,515행', sub: 'Tier별 훈련에 실사용' },
              { label: 'DB 크기', value: '약 12 GB', sub: 'SQLite 파일 (v24)' },
            ].map(s => (
              <div key={s.label} className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-blue-800">{s.value}</p>
                <p className="text-xs text-blue-600 font-semibold mt-0.5">{s.label}</p>
                <p className="text-xs text-gray-500 mt-0.5">{s.sub}</p>
              </div>
            ))}
          </div>

          <h4 className={H4}>Tier별 학습 데이터 규모 (ml_feature_label 실측)</h4>
          <ReportTable
            headers={['Tier', '기업 규모', '행 수', '부도율', '비고']}
            rows={[
              ['T1', '대기업', '101,392행', '0.13%', '샘플링 없이 전량 사용. Fold당 부도 건수 1~15건'],
              ['T2', '중소기업 + 중견기업', '3,948,822행', '0.44%', '생존 35만 건 샘플링. 부도 18,030건 전수'],
              ['T3', '소기업', '1,101,301행', '0.86%', '생존 20만 건 샘플링. 부도 9,492건 전수'],
              ['전체 (Champion)', '전체', '5,151,515행', '0.54%', 'Champion 단일 모델 학습 기반'],
            ]}
          />
          <h4 className={H4}>기업 모집단 구성 (60,000개)</h4>
          <ReportTable
            headers={['구분', '기업 수', '비중', '설명']}
            rows={[
              ['정상 (NORMAL)', '약 47,400개', '79%', '전체 관찰 기간 중 부도 없는 기업'],
              ['부도 (DEFAULT)', '약 8,400개', '14%', '관찰 기간 중 부도 발생 기업 (3,951개는 선행 KPI 완전 적용)'],
              ['회생 (RECOVERY)', '약 4,200개', '7%', '부도 후 워크아웃·회생절차 통해 복귀'],
            ]}
          />

          <h4 className={H4}>업종 분포 (14개 업종 코드)</h4>
          <ReportTable
            headers={['업종 코드', '업종명', '기업 비중', '기본 부도율']}
            rows={[
              ['K00', '농림어업', '2.0%', '1.5%'],
              ['K01A', '섬유·의류 제조', '10.0%', '3.5%'],
              ['K01B', '첨단·자동차부품 제조', '6.0%', '2.5%'],
              ['K02', '건설', '9.0%', '4.0%'],
              ['K03', '도소매', '12.0%', '3.8%'],
              ['K04', '서비스업', '14.0%', '2.8%'],
              ['K05', 'IT·정보통신', '8.0%', '2.2%'],
              ['K06', '의료·바이오', '4.0%', '2.0%'],
              ['K07', '화학·소재', '7.0%', '3.0%'],
              ['K08', '운수·물류', '8.0%', '3.2%'],
              ['K09', '부동산', '6.0%', '4.5%'],
              ['K10', '금속·기계', '6.0%', '3.3%'],
              ['K11', '식음료', '4.0%', '2.7%'],
              ['K12', '에너지·환경', '~2.3%', '2.9%'],
              ['K13', '에너지·신재생', '~1.7%', '3.1%'],
            ]}
          />

          <h4 className={H4}>거시경제 국면 8개 정의 (시계열 현실성 확보)</h4>
          <ReportTable
            headers={['국면', '기간', '리스크 계수', '설명']}
            rows={[
              ['P1 일반 성장기', '2017-01 ~ 2018-06', '0.85', '기준금리 인상 전 완만한 성장'],
              ['P2 미중 무역분쟁', '2018-07 ~ 2019-06', '1.20', '대외 불확실성, 수출 위축'],
              ['P3 저금리 안정기', '2019-07 ~ 2019-12', '0.80', '금리 인하 기조, 여신 확대'],
              ['P4 COVID 충격', '2020-01 ~ 2020-09', '1.80', '급격한 경기 수축, 부도율 급등'],
              ['P5 경기 회복기', '2020-10 ~ 2021-12', '0.90', '정책 지원 + 리오프닝 효과'],
              ['P6 인플레이션', '2022-01 ~ 2022-12', '1.35', '금리 급등, 원가 압박'],
              ['P7 고금리 긴축기', '2023-01 ~ 2024-06', '1.45', '기준금리 3.5% 고착, 부실 누적'],
              ['P8 연착륙 국면', '2024-07 ~ 2025-12', '1.10', '점진적 금리 인하, 여전한 건전성 우려'],
            ]}
          />

          <h4 className={H4}>주요 피처 테이블 구조</h4>
          <ReportTable
            headers={['테이블', '행 수', '피처 수', '주요 내용']}
            rows={[
              ['dim_company', '60,000', '25+', '기업 마스터: 업종, 규모, 설립연도, 상장 여부, RM 등'],
              ['fact_monthly_signal (S03~S07)', '약 510만', '80+', '월별 재무·비재무 지표 (부채비율, DSCR, 연체일수, EWS점수 등)'],
              ['fact_facility / fact_collateral (S08)', '약 16만', '15+', '여신 시설 12만 건, 담보 6만 건'],
              ['fact_ecl (S10~S27)', '약 510만', '8', 'IFRS9 Stage, PD/LGD/EAD/ECL'],
              ['ml_feature_label', '약 510만', '108', 'Walk-forward용 학습 피처 + 타깃 레이블 완성본'],
              ['ml_walk_forward_splits', '12개 fold', '5', 'train_start/end/test_start/test_end/fold_id'],
              ['model_registry', '복수', '10', '챔피언 모델 추적 (champion_flag)'],
              ['model_performance_monthly', 'fold×월', '10', 'AUROC, KS, Brier score 추적'],
            ]}
          />
        </Collapsible>

        <Collapsible title="2-B.2 학습 데이터 생성 전략 — 합성 데이터의 설계 원칙">
          <p className={P}>
            실제 은행 데이터의 접근성 제약, 개인정보 보호 규정, 부도 기업 데이터의 희소성 문제를
            극복하기 위해 통계적으로 현실적인 합성(Synthetic) 데이터 생성 방식을 채택했습니다.
            이 방식은 실제 데이터의 통계적 특성(분포, 상관관계, 시계열 패턴)을 최대한 재현하면서,
            모델 개발에 필요한 충분한 부도 사례를 확보합니다.
          </p>

          <InfoCard title="핵심 설계 원칙 5가지" color="blue">
            <ul className={UL}>
              <li><strong>① 시나리오 기반 경로 생성</strong> — 단순 랜덤이 아닌 NORMAL/DEFAULT/RECOVERY 세 경로를 명시적으로 정의하고, 각 경로 내에서 ACUTE·CHRONIC·EVENT 세 부도 유형을 별도 시뮬레이션</li>
              <li><strong>② 거시경제 국면 반영</strong> — 8개 국면별 리스크 계수를 모든 피처에 곱하여 실제 경기 사이클 패턴 재현. COVID 충격기(P4)에 부도율 약 2배 상승</li>
              <li><strong>③ MNAR(Missing Not At Random) 결측 패턴</strong> — 결측이 데이터 수집 실패가 아닌 기업 특성(소기업은 공시 의무 없음)에 기인함을 반영. 규모·업종별 차등 결측률 적용</li>
              <li><strong>④ Data Leakage 방지</strong> — Oracle 피처(미래 정보를 내포한 ews_score, seizure_flag, ifrs9_stage_cd 등 20+개)를 학습 피처에서 명시적 제외</li>
              <li><strong>⑤ Walk-Forward 시간 순서 보존</strong> — 12개 fold 각각의 train/test 경계가 시간 축 기준으로 엄격히 분리. k-fold 방식의 미래 정보 누수 원천 차단</li>
            </ul>
          </InfoCard>

          <h4 className={H4}>부도 경로별 EWS 점수 생성 로직</h4>
          <ReportTable
            headers={['경로 유형', '점수 생성 방식', '부도 이전 신호 패턴', '적합 업종']}
            rows={[
              ['ACUTE (급성)', '정상 점수 유지 → 부도 3~6개월 전 급락 (Sigmoid 함수)', '갑작스러운 D등급 전환, 공공이벤트 급증', '도소매, 건설'],
              ['CHRONIC (만성)', '관찰 시작 18~24개월 전부터 점진적 하락 (선형+노이즈)', 'B→C→D 순차 하락, 재무비율 장기 악화', '제조, 섬유'],
              ['EVENT (이벤트)', '외부 이벤트 발생 직후 급락, 이후 완만한 하락', '압류/소송 선행 후 EWS 악화, 소송 건수 급증', '부동산, 서비스'],
            ]}
          />

          <h4 className={H4}>KSIC 버전 플래그 처리 (현실 반영)</h4>
          <p className={P}>
            한국표준산업분류(KSIC)가 2024년 7월 KSIC-10에서 KSIC-11로 개정됨에 따라,
            시계열 데이터에 이종 코드 체계가 혼재합니다. 학습 데이터에 <code className="bg-gray-100 px-1 rounded">ksic_version_flag</code>
            컬럼을 추가(KSIC-10: 0, KSIC-11: 1)하여 모델이 이를 피처로 활용할 수 있도록 설계했습니다.
          </p>
        </Collapsible>

        <Collapsible title="2-B.3 Walk-Forward 검증 설계 (12-fold)">
          <p className={P}>
            시계열 금융 데이터에서 단순 k-fold 검증은 미래 정보가 과거 학습 데이터에 포함되는
            'Temporal Data Leakage' 문제가 발생합니다. 이를 방지하기 위해 Walk-Forward
            교차검증을 적용하며, 각 fold는 다음 규칙을 따릅니다.
          </p>
          <InfoCard title="Walk-Forward Fold 구조 (실제 적용)" color="gray">
            <div className="font-mono text-xs text-gray-700 space-y-0.5">
              <p>Fold 01: Train 2017-01~2021-12 → Test 2022-01~2022-04</p>
              <p>Fold 02: Train 2017-05~2022-04 → Test 2022-05~2022-08</p>
              <p>Fold 03: Train 2017-09~2022-08 → Test 2022-09~2022-12</p>
              <p>Fold 04: Train 2018-01~2022-12 → Test 2023-01~2023-04</p>
              <p className="text-gray-400">... (4개월씩 전진)</p>
              <p>Fold 11: Train 2020-05~2025-04 → Test 2025-05~2025-08</p>
              <p>Fold 12: Train 2020-09~2025-08 → Test 2025-09~2025-12</p>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              ※ 타깃: 6개월 내 부도 여부 (label_default_6m). T1은 Fold 4 테스트 기간에 부도 기업 0건으로 자동 스킵 → 11-Fold 검증.
            </p>
          </InfoCard>
          <ReportTable
            headers={['검증 지표', '목표값', '의미']}
            rows={[
              ['AUROC (평균)', '≥ 0.82', '부도/정상 기업을 얼마나 잘 분리하는가'],
              ['KS 통계 (평균)', '≥ 0.45', '누적 분포 최대 분리도'],
              ['Brier Score', '≤ 0.08', '확률 예측의 캘리브레이션 정확도'],
              ['Fold 간 AUROC 표준편차', '≤ 0.03', '모델의 시계열 안정성'],
              ['최악 Fold AUROC', '≥ 0.75', 'COVID 충격기 등 극단 국면에서의 성능'],
            ]}
          />
        </Collapsible>

        <Collapsible title="2-B.4 피처 엔지니어링 상세 (108개 피처)">
          <p className={P}>
            최종 학습 피처 108개는 5개 카테고리로 구성됩니다. Oracle 피처(미래 정보 누수 위험)
            20+개는 명시적으로 제외되었으며, 각 피처의 Data Leakage 위험도가 3단계로 분류됩니다.
          </p>
          <ReportTable
            headers={['피처 카테고리', '피처 수', '대표 피처', '비고']}
            rows={[
              ['재무 원본', '약 30개', '부채비율, 유동비율, ROE, DSCR, 매출성장률', '연간 재무제표 월별 선형 보간'],
              ['연체·부실 행동', '약 15개', 'DPD(연체일수), 한도사용률, 이자연체 여부', '일배치 데이터에서 월말 집계'],
              ['거래행동', '약 20개', '일평균잔액, 입출금비율, 급여이체 여부, 카드지출변화율', '수신 원장 월집계'],
              ['공공·외부이벤트', '약 15개', '소송건수_12m, 압류이력, 세금체납일수', '외부 데이터 소스 연계 필요'],
              ['시계열 파생', '약 28개', '부채비율_3m변화, EWS이동평균, 점수기울기_6m', '원본 피처의 시계열 변환'],
            ]}
          />
          <InfoCard title="Oracle 피처 제외 목록 (Data Leakage 방지)" color="red">
            <p className="text-xs text-gray-700 mb-1">아래 피처들은 부도 발생 후 데이터를 역산하여 생성되었거나, 부도 시점 정보를 직접 내포합니다.</p>
            <div className="font-mono text-xs text-red-700 space-y-0.5">
              <p>Level 1 (직접 누수): ews_score*, ews_score_change_3m, legal_risk_score, supply_chain_risk_score</p>
              <p>Level 1 (이진 트리거): seizure_flag, bankruptcy_filing_flag, key_customer_default_flag</p>
              <p>Level 1 (IFRS9 결과): asset_quality_cd, ifrs9_stage_cd</p>
              <p>Level 2 (간접 누수): pd_12m_forecast, ecl_amount_억, recovery_rate_expectation</p>
            </div>
            <p className="text-xs text-gray-500 mt-1">* ews_score는 학습 타깃에 영향을 주는 방식으로 생성됨 — 학습 피처로 사용 시 순환 참조 문제 발생</p>
          </InfoCard>
        </Collapsible>

        <Collapsible title="2-B.5 검증용 DB — demo.db (운영 시뮬레이션)">
          <p className={P}>
            검증용 DB는 학습 DB와 별개로, iM뱅크의 실제 운영 환경을 시뮬레이션하기 위해
            생성됩니다. 학습 DB가 모델 개발에 집중한다면, 검증용 DB는 시스템 화면의 모든
            기능(경보센터, RM 포트폴리오, 담보 이력 등)이 실제처럼 동작하는 것을 목적으로 합니다.
          </p>
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              { label: '기업 수', value: '20,000개', sub: 'iM뱅크 실제 여신 규모 반영' },
              { label: '기간', value: '36개월', sub: '2023-01 ~ 2025-12' },
              { label: '총 신호 행', value: '약 720,000행', sub: '20,000 × 36개월' },
              { label: 'DB 크기', value: '약 580 MB', sub: '선행지표 5종 포함' },
            ].map(s => (
              <div key={s.label} className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-green-800">{s.value}</p>
                <p className="text-xs text-green-600 font-semibold mt-0.5">{s.label}</p>
                <p className="text-xs text-gray-500 mt-0.5">{s.sub}</p>
              </div>
            ))}
          </div>
          <ReportTable
            headers={['테이블', '행 수', '설명']}
            rows={[
              ['demo_company', '20,000', '기업 마스터 (지역·업종·규모 iM뱅크 분포 반영)'],
              ['demo_monthly_signal', '720,000', '월별 EWS 신호 (ews_tier, data_completeness_pct 포함)'],
              ['demo_facility', '~40,000', '여신 시설 (운전·시설·무역금융·보증)'],
              ['demo_collateral', '~20,000', '담보 (부동산·기계·무담보, LTV 이력)'],
              ['demo_ecl', '~720,000', 'IFRS9 ECL (Stage, PD/LGD/EAD)'],
              ['demo_ews_transaction', '~720,000', '월별 거래행동 선행지표'],
              ['demo_ews_public_event', '~15,000', '공공이벤트 (압류·체납·소송 등)'],
              ['demo_ews_news_monthly', '~173,000', '뉴스 감성 월집계'],
              ['demo_ews_market_signal', '~7,300', '시장신호 (상장사 203개)'],
              ['demo_ews_supply_chain', '~22,400', '공급망 위험 관계'],
              ['demo_ews_action', '~50,000', '경보 액션 이력 (RM 추적)'],
              ['demo_rm', '60', 'RM 정보 (15개 지점 × 4명)'],
            ]}
          />
        </Collapsible>

        {/* ────────────────────────────────── */}
        {/* 3. EWS 이론적 배경                */}
        {/* ────────────────────────────────── */}
        <h2 className={H2}>3. EWS 판단의 이론적 배경</h2>

        <h3 className={H3}>3.1 EWS 점수 산출 프레임워크</h3>
        <p className={P}>
          EWS 점수는 크게 두 단계로 산출됩니다. 먼저 재무·비재무·선행 지표를 가중 합산하여
          원점수(raw_ews_score)를 계산하고, 이를 데이터 완성도(data_completeness_pct)로 조정한
          신뢰 조정 점수(confidence_adj_score)를 최종 EWS 점수로 사용합니다.
        </p>

        <InfoCard title="EWS 점수 산출 공식" color="blue">
          <div className="font-mono text-sm space-y-1">
            <p>raw_ews_score = Σ (지표값 × 가중치) — Sigmoid 정규화 → [0, 100]</p>
            <p>confidence_adj_score = max(1, raw_score − (1 − completeness_pct/100) × 25)</p>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            ※ 데이터 완성도 60% 기업의 경우: 원점수에서 최대 10점 하향 조정 가능
          </p>
        </InfoCard>

        <Collapsible title="3.2 피처 카테고리 및 가중치 구조">
          <ReportTable
            headers={['피처 카테고리', '대표 지표', '가중치(기준)', '신호 방향']}
            rows={[
              ['재무제표', '부채비율, DSCR, 유동비율, ROE', '30%', '↓악화시 EWS 점수 하락'],
              ['거래행동', '일평균잔액, 지연건수, 급여이체', '25%', '잔액감소·지연증가시 하락'],
              ['공공이벤트', '압류, 세금체납, 감사의견 비적정', '15%', '이벤트 발생시 급락'],
              ['뉴스감성', '부정기사 비율, 평균감성점수', '15%', '부정 증가시 하락'],
              ['시장신호', 'CDS스프레드, 주가변화율', '10%', '스프레드 확대시 하락'],
              ['공급망', '전이위험점수, 고위험 거래선 비율', '5%', '연계 부실 위험시 하락'],
            ]}
          />
          <p className="text-xs text-gray-500">
            ※ 실제 모델에서는 LightGBM SHAP 값 기반으로 피처 기여도가 동적으로 결정됩니다.
          </p>
        </Collapsible>

        <Collapsible title="3.3 데이터 완성도 Tier 체계">
          <p className={P}>
            선행지표의 가용성은 기업 규모에 따라 크게 다릅니다. 이를 반영하기 위해 세 개의 Tier를
            정의하고, Tier별로 상이한 모델 앙상블 전략을 적용합니다.
          </p>
          <ReportTable
            headers={['Tier', '대상', '완성도 범위', '학습 데이터', '구현 상태']}
            rows={[
              ['T1 (완전)', '대기업', '75~95%', '101,392행 / AUROC 0.9866 / KS 0.9737', '✓ 구현 완료 (lgbm_t1.pkl)'],
              ['T2 (표준)', '중소·중견기업', '45~75%', '368,030행 / AUROC 0.9998 / KS 0.9935', '✓ 구현 완료 (lgbm_t2.pkl)'],
              ['T3 (기본)', '소기업', '15~50%', '209,492행 / AUROC 0.9997 / KS 0.9905', '✓ 구현 완료 (lgbm_t3.pkl)'],
            ]}
          />
          <InfoCard title="모델 적응성 원칙" color="green">
            <ul className={UL}>
              <li>평가 시점에 특정 피처가 없더라도 이를 결측치로 처리하고 모델이 학습한 대체 패턴 적용</li>
              <li>완성도가 낮을수록 신뢰 구간이 넓어지며, 이는 최종 점수에 보수적 조정으로 반영</li>
              <li>신규 데이터 소스 추가 시 기존 모델 재학습 없이 Tier 상향 가능한 구조</li>
            </ul>
          </InfoCard>
        </Collapsible>

        <Collapsible title="3-B. Tier별 독립 ML 모델 — 실제 학습 결과" defaultOpen>
          <p className={P}>
            T1/T2/T3 세 가지 Tier에 대해 각각 독립된 LightGBM 모델을 학습하였습니다.
            동일한 학습 DB(ews_corporate_v24.db, 5,151,515행)에서 기업 규모 기준으로 서브셋을 분리하고,
            Walk-Forward 12-Fold 교차검증으로 성능을 검증한 실측 결과입니다.
          </p>
          <ReportTable
            headers={['모델', '대상 규모', '학습 행 수', '부도율', 'Walk-Forward AUROC', 'KS 통계', 'AP', 'Fold 수']}
            rows={[
              ['T1 — 대기업', '대기업', '101,392', '0.13%', '0.9866', '0.9737', '0.7279', '11 (Fold 4 스킵)'],
              ['T2 — 중소·중견', '중소기업 + 중견기업', '368,030 (샘플)', '4.90%', '0.9998', '0.9935', '0.9977', '12'],
              ['T3 — 소기업', '소기업', '209,492 (샘플)', '4.53%', '0.9997', '0.9905', '0.9957', '12'],
            ]}
          />
          <InfoCard title="T1 성능 해석 — AP 0.7279가 낮은 이유" color="yellow">
            <p className="text-xs text-gray-700">
              T1(대기업)의 AP(Average Precision)가 T2/T3 대비 현저히 낮은 것은 Fold당 부도 건수가
              1~15건에 불과하기 때문입니다. 부도 1건인 Fold에서는 AP=1.0이 되거나 0에 가까워지는
              극단적 분산이 발생합니다. 실운영에서는 외부 신용평가사 데이터(한국기업평가, NICE 등)와
              채권시장 신호를 추가하여 보완해야 합니다.
            </p>
          </InfoCard>
          <InfoCard title="높은 AUROC 해석 주의 (합성 데이터 Oracle 효과)" color="red">
            <p className="text-xs text-gray-700">
              T2/T3의 AUROC 0.999+ 는 합성 데이터 생성 시 <code className="bg-red-50 px-1 rounded">risk_factor</code>
              (부도 시점 기반)가 모든 피처에 반영된 Oracle 오염 효과입니다.
              실데이터 기반 EWS 모델의 기대 AUROC는 <strong>0.80~0.88</strong>,
              KS는 <strong>0.50~0.60</strong> 수준입니다.
            </p>
          </InfoCard>
          <h4 className={H4}>Tier별 실제 Top 10 피처 (학습 결과 기준)</h4>
          <ReportTable
            headers={['순위', 'T1 (대기업)', 'T2 (중소·중견)', 'T3 (소기업)']}
            rows={[
              ['1', 'lawsuit_amount_억', 'tax_lien_amount_억', 'tax_lien_amount_억'],
              ['2', 'tax_lien_amount_억', 'payroll_amount_pct', 'payroll_amount_pct'],
              ['3', 'icr_pct_rank', 'supplier_hhi', 'supplier_hhi'],
              ['4', 'electricity_usage_idx', 'social_insurance_dropout_flag', 'lawsuit_amount_억'],
              ['5', 'trade_balance_change_pct', 'tax_arrears_months', 'social_insurance_dropout_flag'],
              ['6', 'tax_arrears_months', 'lawsuit_amount_억', 'lawsuit_count_12m'],
              ['7', 'lawsuit_count_12m', 'lawsuit_count_12m', 'tax_arrears_months'],
              ['8', 'social_insurance_dropout_flag', 'industry_cd', 'industry_cd'],
              ['9', 'audit_opinion_qualified_flag', 'audit_opinion_qualified_flag', 'trade_balance_change_pct'],
              ['10', 'sales_growth_pct', 'trade_balance_change_pct', 'news_sentiment_score'],
            ]}
          />
          <p className="text-xs text-gray-500 mt-1">
            ※ 세 Tier 공통으로 <strong>세금 체납(tax_lien_amount_억, tax_arrears_months)</strong>,
            <strong>급여 체불(payroll_amount_pct)</strong>, <strong>소송(lawsuit_amount_억)</strong>이
            상위권을 점유. 합성 데이터 구조상 법적·세무 신호가 부도 경로에 가장 직접적으로 연결되어 있음.
          </p>
          <h4 className={H4}>Tier별 LightGBM 파라미터 차이</h4>
          <ReportTable
            headers={['파라미터', 'T1 (대기업)', 'T2 (중소·중견)', 'T3 (소기업)', '이유']}
            rows={[
              ['num_leaves', '31', '63', '47', 'T1 소규모 데이터 과적합 방지'],
              ['min_child_samples', '10', '50', '30', 'T1 부도 건수 극소 → 최소 노드 완화'],
              ['n_estimators', '400', '500', '400', 'T2 대용량 데이터, 더 많은 트리 허용'],
              ['reg_lambda', '2.0', '1.0', '1.5', 'T1 강한 정규화, T2 완화'],
              ['scale_pos_weight', '자동 (부도율 기반)', '자동', '자동', '불균형 클래스 자동 보정'],
            ]}
          />
        </Collapsible>

        <Collapsible title="3.4 생존 분석 및 Walk-Forward 검증">
          <p className={P}>
            EWS 모델의 예측력 검증에는 시계열 데이터의 특성을 반영한 Walk-Forward 교차검증이 적용됩니다.
            단순 k-fold 교차검증은 미래 정보 누수(leakage) 문제로 시계열 데이터에 부적합합니다.
          </p>
          <ReportTable
            headers={['검증 기법', '설명', '적용 이유']}
            rows={[
              ['Walk-Forward CV', '12개 fold, 각 fold는 시간 순서 유지', '미래 데이터 누수 방지'],
              ['생존 분석', 'Cox PH 모델 기반 부도 위험도 산출', '검열(censored) 데이터 처리'],
              ['AUROC', '0.82 목표 (C/D등급 탐지력)', '모델 변별력 측정'],
              ['KS 통계', '0.45 이상 목표', '부도/정상 분포 분리도'],
              ['선행시간 분석', '부도 3~6개월 전 경보 비율', '조기 경보력 측정'],
            ]}
          />
        </Collapsible>

        {/* ────────────────────────────────── */}
        {/* 4. 감독 규정 호환성                */}
        {/* ────────────────────────────────── */}
        <h2 className={H2}>4. 감독 규정 호환성</h2>

        <p className={P}>
          본 EWS 시스템은 국내 금융감독 체계 및 국제 회계기준과의 정합성을 유지하도록 설계되었습니다.
          주요 준거 규정은 다음과 같습니다.
        </p>

        <Collapsible title="4.1 자산건전성 분류 기준 (금융감독원)" defaultOpen>
          <p className={P}>
            금융감독원의 「은행업감독규정」 제29조 및 「기업신용위험 상시평가 모범규준」에 따른
            자산건전성 5단계 분류 체계를 EWS 등급과 연계하여 적용합니다.
          </p>
          <ReportTable
            headers={['자산건전성 분류', '기준', 'EWS 등급 매핑', '충당금 적립률(최소)']}
            rows={[
              ['정상 (NORMAL)', '원금·이자 정상 상환, 재무 건전', 'A등급', '0.5%'],
              ['요주의 (PRECAUTIONARY)', '1~3개월 연체, 재무 악화 징후', 'B~C등급', '2%'],
              ['고정 (SUBSTANDARD)', '3개월 이상 연체, 부분 회수 가능', 'C~D등급', '20%'],
              ['회수의문 (DOUBTFUL)', '심각한 회수 불확실', 'D등급', '50%'],
              ['추정손실 (LOSS)', '회수 불가능', 'D등급', '100%'],
            ]}
          />
        </Collapsible>

        <Collapsible title="4.2 IFRS9 신용손실 충당금 체계">
          <p className={P}>
            국제회계기준위원회(IASB)의 IFRS9 금융상품 기준에 따라 기대신용손실(ECL: Expected Credit Loss)
            모형을 적용합니다. Stage 분류는 신용 위험의 유의한 증가 여부를 기준으로 합니다.
          </p>
          <ReportTable
            headers={['Stage', '정의', '충당금 산출 기간', 'EWS 연계 기준']}
            rows={[
              ['Stage 1', '최초 인식 이후 신용 위험 유의적 증가 없음', '12개월 기대신용손실', 'EWS A등급, 연체 0일'],
              ['Stage 2', '신용 위험 유의적 증가', '전체 존속 기간 기대신용손실', 'EWS B~C등급, 연체 1~89일'],
              ['Stage 3', '신용 손상 발생', '전체 존속 기간 기대신용손실', 'EWS D등급, 연체 90일 이상'],
            ]}
          />
          <InfoCard title="ECL 산출 공식" color="purple">
            <p className="font-mono text-sm">ECL = PD × LGD × EAD × DF</p>
            <div className="text-xs text-gray-600 mt-2 space-y-1">
              <p>• PD (Probability of Default): EWS 점수 기반 부도 확률</p>
              <p>• LGD (Loss Given Default): 담보 종류 및 LTV 반영 (부동산 30~50%, 무담보 60~80%)</p>
              <p>• EAD (Exposure at Default): 현재 잔액 + 미인출 한도 × CCF</p>
              <p>• DF (Discount Factor): 할인율 적용 현재가치</p>
            </div>
          </InfoCard>
        </Collapsible>

        <Collapsible title="4.3 기업신용위험 상시평가 모범규준 대응">
          <ReportTable
            headers={['모범규준 요건', '시스템 대응', '관련 화면']}
            rows={[
              ['분기별 이상 징후 모니터링', '월별 EWS 점수 산출 및 C/D 경보 자동 생성', 'EWS 경보센터'],
              ['거래행태 분석', '월별 거래행동 데이터(demo_ews_transaction) 분석', '기업 조회 → 선행 신호 탭'],
              ['외부 정보 활용', '공공이벤트·뉴스감성·시장신호 수집 및 반영', '기업 조회 → 선행 신호 탭'],
              ['공급망 위험 평가', '주요 거래선 신용 위험 연계 분석', '기업 조회 → 공급망 위험'],
              ['RM 액션 이행 관리', '경보 액션 상태 추적(OPEN/IN_PROGRESS/COMPLETED)', '경보 액션 관리'],
              ['위험 집중도 관리', '업종별·지역별·규모별 집중도 한도 모니터링', '집중도 한도 관리'],
              ['코베넌트 점검', '재무 특약 위반 여부 월별 자동 점검', '코베넌트 모니터링'],
            ]}
          />
        </Collapsible>

        <Collapsible title="4.4 바젤 III / 내부등급법(IRB) 관련">
          <p className={P}>
            기업여신 EWS는 바젤 III 내부등급법(IRB: Internal Ratings-Based Approach) 적용 은행의
            위험 가중 자산(RWA) 산출과 연계될 수 있습니다. 본 시스템의 PD 추정치는 IRB 요건에 부합하는
            방식으로 산출됩니다.
          </p>
          <ReportTable
            headers={['바젤 III 요건', '시스템 대응']}
            rows={[
              ['1년 PD 추정 (평균 PD 기준)', 'Walk-forward CV로 검증된 시계열 PD 추정 모델'],
              ['PD 재보정 (calibration)', '연간 실제 부도율과의 비교 및 보정 기능'],
              ['모델 검증 (validation)', 'AUROC, KS, 분류 행렬 등 모델 성능 화면 제공'],
              ['경기순응성 완화', '거시경제 국면(8개) 반영 전이 확률 조정'],
              ['장기 평균 PD (TTC)', '경기 중립적 PD 산출 로직 포함'],
            ]}
          />
        </Collapsible>

        {/* ────────────────────────────────── */}
        {/* 5. 데이터 활용 방법                */}
        {/* ────────────────────────────────── */}
        <h2 className={H2}>5. 데이터 활용 방법 (이해관계자별)</h2>

        <Collapsible title="5.1 현업 여신 담당자 (Credit Officer)" defaultOpen>
          <div className="grid grid-cols-2 gap-3">
            <InfoCard title="일상적 모니터링" color="blue">
              <ul className={UL}>
                <li>매월 초 EWS 경보센터에서 C/D 등급 기업 확인</li>
                <li>신규 경보 기업에 대한 액션 플랜 수립 (방문/전화/서류요청)</li>
                <li>기한 초과 액션 현황 모니터링 (기한 초과 시 빨간색 표시)</li>
                <li>월간 EWS 보고서로 포트폴리오 전체 흐름 파악</li>
              </ul>
            </InfoCard>
            <InfoCard title="개별 기업 심층 분석" color="green">
              <ul className={UL}>
                <li>기업 조회 → EWS 점수 추이 차트로 악화 시점 확인</li>
                <li>선행 신호 탭 → 데이터 완성도 및 공공이벤트 확인</li>
                <li>담보 이력 탭 → LTV 변화 및 담보 충분성 검토</li>
                <li>코베넌트 탭 → 특약 위반 이력 확인</li>
              </ul>
            </InfoCard>
          </div>
          <InfoCard title="의사결정 활용 포인트" color="yellow">
            <ReportTable
              headers={['상황', '확인 화면', '의사결정 기준']}
              rows={[
                ['신규 여신 심사', '기업 조회 → EWS 신호 + 재무 탭', 'C등급 이상이면 추가 담보 요구'],
                ['기존 여신 갱신', 'EWS 점수 추이 + 공공이벤트', '6개월 이상 B→C 하락 추세 시 조건 강화'],
                ['한도 증액 요청', '포트폴리오 → 집중도 한도', '업종 집중도 한도 초과 여부 확인'],
                ['조기 상환 요청 검토', 'EWS D등급 + 코베넌트 위반', '두 조건 동시 충족 시 조기 상환 사유'],
              ]}
            />
          </InfoCard>
        </Collapsible>

        <Collapsible title="5.2 IT 개발자">
          <p className={P}>
            본 시스템은 FastAPI(백엔드) + React(프론트엔드) + SQLite(검증용 DB) 구조이며,
            실데이터 환경으로의 전환을 위해 데이터 레이어만 교체할 수 있도록 설계되어 있습니다.
          </p>
          <h4 className={H4}>API 구조 (REST)</h4>
          <ReportTable
            headers={['API 그룹', '기본 경로', '주요 엔드포인트', '인증']}
            rows={[
              ['EWS', '/api/ews', 'GET /alerts, GET /grade-distribution, GET /company/{id}/history', '미구현(POC)'],
              ['EWS 고도화', '/api/ews-advanced', 'GET /company/{id}/completeness, transaction, news...', '미구현(POC)'],
              ['기업', '/api/company', 'GET /list, /{id}, /search', '미구현(POC)'],
              ['포트폴리오', '/api/portfolio', 'GET /summary, /concentration', '미구현(POC)'],
              ['ECL', '/api/ecl', 'GET /summary, /trend, /by-grade', '미구현(POC)'],
              ['검색', '/api/search', 'GET /company?q=&region=&limit=', '미구현(POC)'],
            ]}
          />
          <h4 className={H4}>데이터베이스 교체 절차</h4>
          <ol className={OL}>
            <li><code className="bg-gray-100 px-1 rounded">backend/app/core/database.py</code>의 DATABASE_URL을 실 DB URL로 변경</li>
            <li>SQLAlchemy 드라이버 교체 (SQLite → PostgreSQL: psycopg2, Oracle: cx_Oracle)</li>
            <li>각 API 모듈의 SQL 쿼리를 실 테이블명/스키마에 맞게 수정</li>
            <li>인증 미들웨어 추가 (JWT 토큰, LDAP 연동 등)</li>
            <li>환경별 설정 분리 (.env 파일 사용)</li>
          </ol>
        </Collapsible>

        <Collapsible title="5.3 데이터 모델러">
          <p className={P}>
            EWS 모델 개발 및 검증을 담당하는 데이터 모델러를 위한 데이터 활용 가이드입니다.
          </p>
          <h4 className={H4}>학습 데이터 구조</h4>
          <ReportTable
            headers={['테이블', '역할', '피처 수', '레코드 수']}
            rows={[
              ['demo_monthly_signal', '주요 EWS 피처 + 타깃(default_flag)', '20+', '20,000 × 36 = 720,000행'],
              ['demo_ews_transaction', '거래행동 피처 (월별)', '9개', '20,000 × 36 = 720,000행'],
              ['demo_ews_news_monthly', '뉴스감성 피처 (월별)', '6개', '약 173,000행'],
              ['demo_ews_market_signal', '시장신호 피처 (상장사, 월별)', '6개', '약 7,300행'],
              ['demo_ews_supply_chain', '공급망 위험 피처', '5개', '약 22,000행'],
              ['demo_ews_public_event', '공공이벤트 (사건별)', '6개', '약 15,000건'],
            ]}
          />
          <h4 className={H4}>모델 학습 권장 사항</h4>
          <ul className={UL}>
            <li><strong>타깃 정의</strong>: 12개월 내 부도 여부 (binary) 또는 부도까지 잔여 기간 (survival)</li>
            <li><strong>검증 전략</strong>: Walk-Forward CV 사용 (시간 순서 유지, 최소 12 fold)</li>
            <li><strong>결측치 처리</strong>: Tier별 결측 패턴이 다름. MNAR(Not at Random) 처리 필요</li>
            <li><strong>클래스 불균형</strong>: 부도율 ~12% → SMOTE 또는 class_weight 조정 권장</li>
            <li><strong>피처 중요도</strong>: SHAP 값 기반 해석 가능성(Explainability) 확보 필수</li>
            <li><strong>데이터 누수 주의</strong>: 미래 정보(부도 이후 데이터)가 학습 데이터에 포함되지 않도록 엄격한 시점 관리</li>
          </ul>
        </Collapsible>

        {/* ────────────────────────────────── */}
        {/* 6. 기술 아키텍처                   */}
        {/* ────────────────────────────────── */}
        <h2 className={H2}>6. 기술 아키텍처</h2>

        <Collapsible title="6.1 전체 시스템 구성도" defaultOpen>
          <div className="bg-gray-50 rounded-lg p-4 font-mono text-xs text-gray-700 mb-4 border border-gray-200">
            <pre>{`
┌──────────────────────────────────────────────────────────────┐
│                     프론트엔드 (React + TypeScript)            │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌───────────────┐  │
│  │Dashboard│  │EWSAlerts│  │Company   │  │SystemReport   │  │
│  │         │  │         │  │Browser   │  │(이 화면)       │  │
│  └─────────┘  └─────────┘  └──────────┘  └───────────────┘  │
│                    Vite + Tailwind CSS                        │
└────────────────────────────┬─────────────────────────────────┘
                             │ HTTP (Axios)
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                    백엔드 (FastAPI)                            │
│  /api/ews    /api/company    /api/ecl    /api/ews-advanced    │
│  /api/portfolio  /api/stress-test  /api/rm  ...              │
│                SQLAlchemy ORM                                 │
└────────────────────────────┬─────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   SQLite DB      │
                    │  (demo/demo.db) │
                    │  ~580MB          │
                    │  20개+ 테이블    │
                    └─────────────────┘
`}</pre>
          </div>
        </Collapsible>

        <Collapsible title="6.2 기술 스택">
          <ReportTable
            headers={['레이어', '기술', '버전', '역할']}
            rows={[
              ['프론트엔드', 'React + TypeScript', '18 / 5', 'SPA UI 렌더링'],
              ['프론트엔드', 'Vite', '5.x', '빌드 도구, HMR'],
              ['프론트엔드', 'Tailwind CSS', '3.x', '유틸리티 CSS 스타일링'],
              ['프론트엔드', 'Recharts', '2.x', '차트 (Line, Bar, Donut)'],
              ['프론트엔드', 'React Router', '6.x', 'SPA 라우팅 (18개 페이지)'],
              ['프론트엔드', 'Axios', '1.x', 'HTTP API 클라이언트'],
              ['백엔드', 'FastAPI', '0.1xx', 'REST API 서버'],
              ['백엔드', 'SQLAlchemy', '2.x', 'ORM, DB 추상화'],
              ['백엔드', 'Uvicorn', '0.3x', 'ASGI 서버'],
              ['데이터베이스', 'SQLite', '3.x', 'POC용 파일 DB (→ 실환경 PostgreSQL/Oracle 교체)'],
              ['데이터 생성', 'Python + NumPy', '3.10+', '합성 데이터셋 생성기'],
            ]}
          />
        </Collapsible>

        <Collapsible title="6.3 데이터베이스 스키마 (주요 테이블)">
          <ReportTable
            headers={['테이블명', '설명', '주요 컬럼', '행 수(예시)']}
            rows={[
              ['demo_company', '기업 마스터', 'borrower_id, company_name, firm_size_cd, industry_cd, region, listed_flag, rm_id', '20,000'],
              ['demo_monthly_signal', '월별 EWS 신호', 'borrower_id, ym, ews_grade, ews_score, ews_tier, data_completeness_pct, ifrs9_stage, seizure_flag, ...', '720,000'],
              ['demo_facility', '여신 시설', 'facility_id, borrower_id, facility_type, committed_amount_억, maturity_ym, collateral_type', '~40,000'],
              ['demo_collateral', '담보 정보', 'collateral_id, borrower_id, collateral_type, appraised_value_억, ltv_pct', '~20,000'],
              ['demo_ecl', 'ECL 충당금', 'borrower_id, ym, stage, ecl_amount_억, pd_value, lgd, ead_억', '~720,000'],
              ['demo_ews_action', '경보 액션', 'action_id, borrower_id, action_type, status, due_date, rm_id', '~50,000'],
              ['demo_rm', 'RM 정보', 'rm_id, rm_name, branch_name, region', '60'],
              ['demo_workout', 'NPL/Workout', 'workout_id, borrower_id, workout_type, original_balance_억, recovery_rate', '~3,800'],
              ['demo_covenant', '코베넌트', 'borrower_id, check_ym, covenant_type, result, actual_value, threshold_value', '~200,000'],
            ]}
          />
        </Collapsible>

        <Collapsible title="6.4 배포 및 운영">
          <h4 className={H4}>POC 환경 실행</h4>
          <div className="bg-gray-900 rounded-lg p-4 font-mono text-xs text-green-400 mb-4">
            <p className="text-gray-400"># 1. 데이터 생성 (최초 1회, 약 56초 소요)</p>
            <p>python demo/generate_dataset.py</p>
            <p className="mt-2 text-gray-400"># 2. 서버 실행</p>
            <p>bash start.sh</p>
            <p className="mt-2 text-gray-400"># 또는 개별 실행</p>
            <p>uvicorn backend.app.main:app --reload --port 8000</p>
            <p>cd frontend && npm run dev  # 포트 3000</p>
          </div>
          <h4 className={H4}>실서버 배포 고려사항</h4>
          <ul className={UL}>
            <li>데이터베이스: SQLite → PostgreSQL 또는 Oracle 교체 필요</li>
            <li>인증: JWT 토큰 기반 인증 추가 (현재 미구현)</li>
            <li>CORS: production 환경에서 특정 도메인만 허용</li>
            <li>환경변수: DATABASE_URL, SECRET_KEY 등 .env 파일 관리</li>
            <li>정적 파일: <code className="bg-gray-100 px-1 rounded">npm run build</code> 후 FastAPI가 서빙</li>
          </ul>
        </Collapsible>

        {/* ────────────────────────────────── */}
        {/* 7. 실데이터 전환 가이드            */}
        {/* ────────────────────────────────── */}
        <h2 className={H2}>7. 실데이터 적용 가이드</h2>

        <p className={P}>
          본 섹션은 iM뱅크의 실제 여신 운영 시스템(CLMS, 여신관리 시스템 등)에서 데이터를 수집하여
          본 EWS 시스템에 연계하고자 하는 IT 담당자 및 데이터 엔지니어를 위한 가이드입니다.
        </p>

        <Collapsible title="7.1 데이터 소스 매핑" defaultOpen>
          <ReportTable
            headers={['EWS 데이터 요소', '실데이터 소스', '수집 주기', '가용성']}
            rows={[
              ['기업 기본정보', 'CLMS 차주 마스터 테이블', '실시간', '높음'],
              ['여신 시설 정보', 'CLMS 여신 원장', '일배치', '높음'],
              ['연체 정보', '연체관리 시스템', '일배치', '높음'],
              ['담보 평가액', '담보관리 시스템', '분기', '높음'],
              ['재무제표', 'KIS/NICE 신용평가 또는 세무청 스크래핑', '연 1회 이상', '중간'],
              ['거래행동 데이터', '수신 원장, 결제 시스템', '월배치', '중간'],
              ['공공이벤트', '국세청API, 대법원 법인등기, 금감원 공시', '주배치', '중간'],
              ['뉴스 감성', '뉴스 API(Naver, BigKinds) + NLP 분석', '일배치', '낮음~중간'],
              ['시장 신호', 'KRX 주가 데이터, 채권 시장 데이터', '일배치', '상장사만 가능'],
              ['공급망 관계', 'DART 공시, SCF 여신 거래처 정보', '분기~반기', '낮음'],
            ]}
          />
        </Collapsible>

        <Collapsible title="7.2 데이터 품질 요건">
          <InfoCard title="필수 데이터 (Tier 관계없이 모든 기업)" color="red">
            <ul className={UL}>
              <li>차주 ID (borrower_id) — 시스템 전체의 Primary Key, 불변 값으로 관리</li>
              <li>기업 기본정보 — 업종코드(KSIC), 규모구분, 소재지</li>
              <li>여신 잔액 및 연체 정보 — 최소 3개월 이력</li>
              <li>한도 사용률 — 약정한도 대비 사용 잔액 비율</li>
            </ul>
          </InfoCard>
          <InfoCard title="권장 데이터 (모델 정확도 향상)" color="yellow">
            <ul className={UL}>
              <li>재무제표 주요 지표 — 부채비율, 유동비율, 영업이익률, DSCR</li>
              <li>거래행동 지표 — 일평균 예금잔액, 입출금 비율</li>
              <li>공공이벤트 — 압류, 세금 체납, 경영진 변경</li>
            </ul>
          </InfoCard>
        </Collapsible>

        <Collapsible title="7.3 실데이터 전환 체크리스트">
          <ReportTable
            headers={['단계', '작업 항목', '담당', '검증 방법']}
            rows={[
              ['① 데이터 연계', '실 DB 연결 및 ETL 파이프라인 구축', 'IT', 'demo.db 데이터와 구조 비교'],
              ['① 데이터 연계', '차주 ID 체계 통일 (borrower_id)', 'IT+현업', '중복·누락 0건 확인'],
              ['② 피처 엔지니어링', '실데이터 기반 피처 계산 로직 구현', '데이터 모델러', 'demo 데이터와 분포 비교'],
              ['② 피처 엔지니어링', 'MNAR 결측 패턴 분석 및 처리', '데이터 모델러', '결측 비율 리포트'],
              ['③ 모델 재학습', '실데이터 기반 EWS 모델 재학습', '데이터 모델러', 'AUROC ≥ 0.75 목표'],
              ['③ 모델 재학습', 'Walk-Forward CV 검증', '데이터 모델러', 'KS 통계 ≥ 0.35'],
              ['④ 시스템 통합', '백엔드 API → 실 DB 쿼리 수정', 'IT', '기존 화면 정상 표시 확인'],
              ['④ 시스템 통합', '인증/권한 체계 구현', 'IT', '역할별 접근 제한 테스트'],
              ['⑤ 운영 전환', '병렬 운영 (기존 시스템 + EWS)', '현업+IT', '3개월 병렬 후 전환'],
              ['⑤ 운영 전환', '임계값 캘리브레이션', '현업+데이터 모델러', '실제 부도율과 예측 PD 비교'],
            ]}
          />
        </Collapsible>

        <Collapsible title="7.4 피처 가용성 차이 대응 전략 (핵심)">
          <p className={P}>
            모델 학습 시점에는 100가지 피처를 활용했더라도, 실제 평가 대상 기업에 대해서는 그보다
            적은 수의 피처만 가용한 경우가 일반적입니다. 이 문제를 해결하기 위한 세 가지 전략을
            적용합니다.
          </p>
          <div className="grid grid-cols-1 gap-3">
            <InfoCard title="전략 1: 피처 완성도 Tier 기반 모델 분리 — 구현 완료" color="blue">
              <p className={P}>
                T1/T2/T3 세 가지 독립 LightGBM 모델이 각각 학습·배포되었습니다 (lgbm_t1/t2/t3.pkl).
                평가 시점에 해당 기업의 firm_size_cd 기반 Tier를 판단하여 적합한 모델을 자동 선택합니다.
              </p>
              <p className="text-xs text-gray-500">
                T1: 101K행 학습, T2: 368K행 (샘플), T3: 209K행 (샘플) |
                재학습은 '모델 성능' 메뉴 → 관리자 비밀번호 입력으로 실행 가능
              </p>
            </InfoCard>
            <InfoCard title="전략 2: 결측치를 정보로 활용 (MNAR 인코딩)" color="green">
              <p className={P}>
                특정 데이터가 없다는 사실 자체가 의미 있는 신호입니다. 예를 들어, 재무제표를
                제출하지 않은 기업은 제출 기업보다 평균적으로 신용 위험이 높습니다. 결측 여부를
                별도 이진 피처로 추가하여 이 정보를 활용합니다.
              </p>
            </InfoCard>
            <InfoCard title="전략 3: 신뢰 조정 점수 (Confidence-Adjusted Score)" color="purple">
              <p className={P}>
                데이터 완성도가 낮을수록 점수의 신뢰 구간이 넓어짐을 반영하여, 원점수에 불확실성
                페널티를 적용합니다. 이는 불완전한 정보에 기반한 과신(overconfidence)을 방지합니다.
              </p>
              <p className="font-mono text-xs bg-white border rounded px-2 py-1 mt-2">
                confidence_adj_score = max(1, raw_score - (1 - completeness) × 25)
              </p>
            </InfoCard>
          </div>
        </Collapsible>

        {/* ────────────────────────────────── */}
        {/* 8. 운영 지표 및 KPI               */}
        {/* ────────────────────────────────── */}
        <h2 className={H2}>8. 운영 지표 및 성과 측정 KPI</h2>

        <Collapsible title="8.1 모델 성능 지표" defaultOpen>
          <ReportTable
            headers={['지표', '목표값', '측정 주기', '설명']}
            rows={[
              ['AUROC', '≥ 0.82', '분기', '부도 기업과 정상 기업의 점수 분리 능력'],
              ['KS 통계', '≥ 0.45', '분기', '누적 분포 함수 최대 차이'],
              ['정밀도 (C/D 등급)', '≥ 0.70', '월간', 'C/D 예측 중 실제 부도 비율'],
              ['재현율 (부도 포착율)', '≥ 0.80', '월간', '실제 부도 기업 중 C/D 예측 비율'],
              ['선행시간 (Lead Time)', '평균 6개월', '반기', '부도 발생 전 C/D 경보 최초 발령 시점'],
              ['Brier Score', '≤ 0.08', '분기', '확률 예측의 보정 정확도'],
            ]}
          />
        </Collapsible>

        <Collapsible title="8.2 운영 효율성 지표">
          <ReportTable
            headers={['지표', '목표값', '설명']}
            rows={[
              ['액션 완료율', '≥ 85%', '경보 발령 후 RM 액션 이행 비율'],
              ['기한 초과율', '≤ 10%', '액션 due_date 초과 비율'],
              ['경보 피로도 (False Positive)', '≤ 30%', 'C/D 경보 후 12개월 내 정상 복귀 비율'],
              ['코베넌트 점검 적시성', '100%', '특약 조항 점검 기한 내 완료율'],
              ['데이터 완성도 개선율', '+5%p / 연', '데이터 소스 추가로 인한 Tier 상향 비율'],
            ]}
          />
        </Collapsible>

        {/* ────────────────────────────────── */}
        {/* 9. 향후 개선 로드맵               */}
        {/* ────────────────────────────────── */}
        <h2 className={H2}>9. 향후 개선 로드맵</h2>

        <div className="grid grid-cols-3 gap-3">
          {[
            {
              phase: 'Phase 1 (단기)', period: '3~6개월',
              items: [
                '✓ T1/T2/T3 Tier별 독립 모델 구현 완료',
                '✓ 모델 재학습 UI (관리자 인증) 구현',
                '실데이터 연계 ETL 구축',
                '재무제표 자동 수집 파이프라인',
                'PostgreSQL 전환',
              ],
              color: 'blue'
            },
            {
              phase: 'Phase 2 (중기)', period: '6~12개월',
              items: [
                '실데이터 기반 T1/T2/T3 모델 재학습',
                'T1 대기업 모델 외부 시장 데이터 보강',
                '뉴스 NLP 파이프라인 구축',
                '공급망 네트워크 분석 고도화',
                '사용자 인증 및 권한 체계',
              ],
              color: 'green'
            },
            {
              phase: 'Phase 3 (장기)', period: '12~24개월',
              items: [
                'GNN 기반 공급망 전이 위험 모델',
                '실시간 이상 탐지 스트리밍',
                'SHAP 기반 설명 가능 AI',
                '감독 규정 자동 보고서',
                'Tier별 임계값 최적화 자동화',
              ],
              color: 'purple'
            },
          ].map(p => (
            <InfoCard key={p.phase} title={`${p.phase} (${p.period})`} color={p.color as any}>
              <ul className="text-xs text-gray-700 space-y-1">
                {p.items.map(item => <li key={item} className={item.startsWith('✓') ? 'text-green-700 font-medium' : ''}>{item.startsWith('✓') ? item : `• ${item}`}</li>)}
              </ul>
            </InfoCard>
          ))}
        </div>

        {/* ────────────────────────────────── */}
        {/* 참고 문헌                          */}
        {/* ────────────────────────────────── */}
        <h2 className={H2}>참고 규정 및 문헌</h2>

        <ul className={UL}>
          <li>금융감독원, 「은행업감독규정」 제29조 (자산건전성 분류 기준), 2024</li>
          <li>금융감독원, 「기업신용위험 상시평가 모범규준」, 2022</li>
          <li>금융감독원, 「IFRS9 도입에 따른 대손충당금 적립기준 적용 관련 감독규정 개정」, 2018</li>
          <li>IASB, IFRS 9 Financial Instruments, 2014</li>
          <li>Basel Committee on Banking Supervision, Basel III: A global regulatory framework, 2010</li>
          <li>금융위원회, 「은행 내부등급법(IRB) 적용 심사 매뉴얼」, 2019</li>
          <li>Chen, T. and Guestrin, C., XGBoost: A Scalable Tree Boosting System, KDD 2016</li>
          <li>Ke, G. et al., LightGBM: A Highly Efficient Gradient Boosting Decision Tree, NIPS 2017</li>
          <li>Altman, E.I., Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy, Journal of Finance, 1968</li>
        </ul>

        {/* ─ 하단 메타 ─ */}
        <div className="mt-10 pt-4 border-t border-gray-200 text-xs text-gray-400">
          <div className="flex justify-between mb-1">
            <span>iM뱅크 기업여신 EWS 시스템 v2.0.0 | POC 환경 | 기준일 2026-03</span>
            <span className="no-print">이 페이지를 인쇄하면 PDF로 저장할 수 있습니다</span>
          </div>
          <p className="text-gray-400">개발: 황원철 (Hwang Weoncheol) — 설계·구현·데이터 생성 파이프라인·ML 모델링·프론트엔드·백엔드 전 영역</p>
        </div>

      </div>
    </>
  );
}

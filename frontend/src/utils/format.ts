// 숫자 포맷팅 유틸리티

/**
 * 금액 포맷 (억원 단위)
 */
export function formatAmount(value: number, unit: 'won' | 'million' | 'billion' | 'trillion' = 'million'): string {
  if (value === null || value === undefined) return '-';

  switch (unit) {
    case 'won':
      return new Intl.NumberFormat('ko-KR').format(value) + '원';
    case 'million':
      return new Intl.NumberFormat('ko-KR').format(value / 1_000_000) + '백만원';
    case 'billion':
      return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 }).format(value / 100_000_000) + '억원';
    case 'trillion':
      return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 }).format(value / 1_000_000_000_000) + '조원';
    default:
      return new Intl.NumberFormat('ko-KR').format(value);
  }
}

/**
 * 억원 단위 포맷 (이미 억 단위인 값)
 */
export function formatEok(value: number, decimals: number = 1): string {
  if (value === null || value === undefined) return '-';
  return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: decimals }).format(value) + '억';
}

/**
 * 퍼센트 포맷
 */
export function formatPercent(value: number, decimals: number = 2): string {
  if (value === null || value === undefined) return '-';
  return value.toFixed(decimals) + '%';
}

/**
 * 비율 포맷 (0.0x -> x%)
 */
export function formatRatio(value: number, decimals: number = 2): string {
  if (value === null || value === undefined) return '-';
  return (value * 100).toFixed(decimals) + '%';
}

/**
 * 날짜 포맷
 */
export function formatDate(dateStr: string, format: 'short' | 'long' | 'full' = 'short'): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);

  switch (format) {
    case 'short':
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    case 'long':
      return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일`;
    case 'full':
      return date.toLocaleString('ko-KR');
    default:
      return dateStr;
  }
}

/**
 * ym (202301) -> "2023-01" 포맷
 */
export function formatYm(ym: number | string): string {
  const s = String(ym);
  if (s.length !== 6) return String(ym);
  return `${s.slice(0, 4)}-${s.slice(4)}`;
}

/**
 * 숫자 포맷 (천단위 콤마)
 */
export function formatNumber(value: number, decimals: number = 0): string {
  if (value === null || value === undefined) return '-';
  return new Intl.NumberFormat('ko-KR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(value);
}

/**
 * EWS 등급 색상 클래스
 */
export function getEWSGradeColorClass(grade: string): string {
  switch (grade) {
    case 'A': return 'text-green-700 font-semibold';
    case 'B': return 'text-yellow-600 font-semibold';
    case 'C': return 'text-orange-600 font-semibold';
    case 'D': return 'text-red-700 font-semibold';
    default: return 'text-gray-600';
  }
}

/**
 * EWS 등급 배경색 클래스
 */
export function getEWSGradeBgClass(grade: string): string {
  switch (grade) {
    case 'A': return 'bg-green-100 text-green-800';
    case 'B': return 'bg-yellow-100 text-yellow-800';
    case 'C': return 'bg-orange-100 text-orange-800';
    case 'D': return 'bg-red-100 text-red-800';
    default: return 'bg-gray-100 text-gray-800';
  }
}

/**
 * EWS 등급 색상 코드 (차트용)
 */
export function getEWSGradeColor(grade: string): string {
  switch (grade) {
    case 'A': return '#27ae60';
    case 'B': return '#f39c12';
    case 'C': return '#e67e22';
    case 'D': return '#e74c3c';
    default: return '#6b7280';
  }
}

/**
 * 자산건전성 분류 색상
 */
export function getClassificationColor(classification: string): string {
  switch (classification) {
    case 'NORMAL': return '#10b981';
    case 'PRECAUTIONARY': return '#f59e0b';
    case 'SUBSTANDARD': return '#f97316';
    case 'DOUBTFUL': return '#ef4444';
    case 'LOSS': return '#dc2626';
    default: return '#6b7280';
  }
}

/**
 * 자산건전성 분류 한글 변환
 */
export function getClassificationLabel(classification: string): string {
  switch (classification) {
    case 'NORMAL': return '정상';
    case 'PRECAUTIONARY': return '요주의';
    case 'SUBSTANDARD': return '고정';
    case 'DOUBTFUL': return '회수의문';
    case 'LOSS': return '추정손실';
    default: return classification;
  }
}

/**
 * 기업 규모 한글 변환
 */
export function getFirmSizeLabel(sizeCode: string): string {
  switch (sizeCode) {
    case 'LARGE': return '대기업';
    case 'MEDIUM': return '중기업';
    case 'SMALL': return '소기업';
    default: return sizeCode;
  }
}

/**
 * 상태 색상 클래스
 */
export function getStatusColorClass(status: string): string {
  const upperStatus = status?.toUpperCase() || '';

  if (['ACTIVE', 'APPROVED', 'NORMAL', 'HEALTHY', 'PASS', 'COMPLETED'].includes(upperStatus)) {
    return 'bg-green-100 text-green-800';
  }
  if (['PENDING', 'REVIEW', 'UNDER_REVIEW', 'WARNING', 'WAIVED', 'ONGOING'].includes(upperStatus)) {
    return 'bg-yellow-100 text-yellow-800';
  }
  if (['REJECTED', 'CRITICAL', 'BREACH', 'ALERT', 'FAILED'].includes(upperStatus)) {
    return 'bg-red-100 text-red-800';
  }
  if (['INACTIVE', 'EXPIRED', 'CLOSED'].includes(upperStatus)) {
    return 'bg-gray-100 text-gray-600';
  }
  return 'bg-blue-100 text-blue-800';
}

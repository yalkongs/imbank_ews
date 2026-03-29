import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { SearchIcon, Building2, AlertTriangle, MapPin } from 'lucide-react';
import { searchApi } from '../utils/api';

interface SearchResult {
  borrower_id: string;
  company_name: string;
  firm_size_cd: string;
  industry_cd: string;
  ews_grade: string | null;
  ews_score: number | null;
  default_flag: boolean;
  rm_name: string | null;
  region: string | null;
}

const GRADE_COLORS: Record<string, string> = {
  A: 'bg-green-100 text-green-700',
  B: 'bg-yellow-100 text-yellow-700',
  C: 'bg-orange-100 text-orange-700',
  D: 'bg-red-100 text-red-700',
};

const REGIONS = [
  { value: '', label: '전체 지역' },
  { value: '수도권', label: '수도권' },
  { value: '대구경북', label: '대구경북' },
  { value: '부산경남', label: '부산경남' },
];

const PAGE_SIZE = 100;

function debounce<T extends (...args: any[]) => any>(fn: T, delay: number) {
  let timer: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

export default function Search() {
  const [query, setQuery] = useState('');
  const [region, setRegion] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const offsetRef = useRef(0);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // 새 검색: 결과 초기화 후 첫 페이지 로드
  const doSearch = useCallback(
    debounce(async (q: string, r: string) => {
      setLoading(true);
      offsetRef.current = 0;
      try {
        const res = await searchApi.searchCompany(q, r, PAGE_SIZE, 0);
        setResults(res.data.results);
        setTotal(res.data.total);
        setHasMore(res.data.has_more);
        offsetRef.current = res.data.results.length;
      } catch {
        setResults([]);
        setTotal(0);
        setHasMore(false);
      } finally {
        setLoading(false);
      }
    }, 250),
    []
  );

  // 추가 로드
  const loadMore = useCallback(async (q: string, r: string) => {
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      const res = await searchApi.searchCompany(q, r, PAGE_SIZE, offsetRef.current);
      setResults(prev => [...prev, ...res.data.results]);
      setHasMore(res.data.has_more);
      offsetRef.current += res.data.results.length;
    } catch {
      // silent
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore]);

  // 검색어/지역 변경 시 새 검색
  useEffect(() => {
    doSearch(query, region);
  }, [query, region, doSearch]);

  // IntersectionObserver: 하단 sentinel 감지 → 추가 로드
  useEffect(() => {
    if (!sentinelRef.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingMore && !loading) {
          loadMore(query, region);
        }
      },
      { threshold: 0.1 }
    );
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, loading, query, region, loadMore]);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">기업 검색</h1>
        <p className="text-gray-500 text-sm">기업명 또는 기업 ID로 검색하세요</p>
      </div>

      {/* 검색 컨트롤 */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="기업명, 기업ID 검색..."
            className="w-full pl-11 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm
                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                       shadow-sm"
          />
          {loading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>

        {/* 지역 필터 */}
        <div className="flex items-center gap-1 bg-white border border-gray-200 rounded-lg px-2 shadow-sm">
          <MapPin size={14} className="text-gray-400 flex-shrink-0" />
          {REGIONS.map((r) => (
            <button
              key={r.value}
              onClick={() => setRegion(r.value)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors whitespace-nowrap ${
                region === r.value
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* 결과 헤더 */}
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm text-gray-500">
          {query
            ? <><span className="font-medium text-gray-800">"{query}"</span> 검색 결과</>
            : region
              ? <><span className="font-medium text-blue-700">{region}</span> 기업 목록</>
              : '전체 기업 목록'
          }
          {' '}— <span className="font-semibold text-gray-900">{total.toLocaleString()}건</span>
          {results.length < total && (
            <span className="text-gray-400"> ({results.length.toLocaleString()}건 로드됨)</span>
          )}
        </p>
      </div>

      {/* 결과 목록 */}
      {results.length === 0 && !loading ? (
        <div className="text-center py-16 text-gray-400">
          <Building2 size={40} className="mx-auto mb-3 opacity-40" />
          <p>검색 결과가 없습니다</p>
        </div>
      ) : (
        <div className="space-y-2">
          {results.map((r) => (
            <div
              key={r.borrower_id}
              className="bg-white border border-gray-200 rounded-lg p-3.5 hover:shadow-md hover:border-blue-200 transition-all cursor-pointer"
              onClick={() => navigate(`/companies?id=${r.borrower_id}`)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <h3 className="font-semibold text-gray-900 truncate">{r.company_name}</h3>
                  {r.ews_grade && (
                    <span className={`flex-shrink-0 px-2 py-0.5 text-xs font-bold rounded-full ${GRADE_COLORS[r.ews_grade] ?? 'bg-gray-100 text-gray-600'}`}>
                      {r.ews_grade}등급
                    </span>
                  )}
                  {r.default_flag && (
                    <span className="flex-shrink-0 flex items-center gap-1 px-2 py-0.5 text-xs bg-red-50 text-red-600 rounded-full">
                      <AlertTriangle size={11} /> 부도
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4 ml-3 flex-shrink-0">
                  <div className="flex flex-wrap gap-2 text-xs text-gray-400">
                    <span>{r.borrower_id}</span>
                    <span>{r.firm_size_cd}</span>
                    <span>{r.industry_cd}</span>
                    {r.region && (
                      <span className="flex items-center gap-0.5 text-blue-500">
                        <MapPin size={10} />{r.region}
                      </span>
                    )}
                    {r.rm_name && <span>담당: {r.rm_name}</span>}
                    {r.ews_score !== null && (
                      <span className="text-gray-500">EWS: <span className="font-mono">{r.ews_score}점</span></span>
                    )}
                  </div>
                  <span className="text-xs text-blue-600 font-medium">상세보기 →</span>
                </div>
              </div>
            </div>
          ))}

          {/* 무한 스크롤 sentinel */}
          <div ref={sentinelRef} className="h-4" />

          {/* 추가 로딩 인디케이터 */}
          {loadingMore && (
            <div className="flex justify-center py-4">
              <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {/* 전체 로드 완료 */}
          {!hasMore && results.length > 0 && results.length === total && (
            <p className="text-center text-xs text-gray-400 py-3">
              전체 {total.toLocaleString()}개 기업 로드 완료
            </p>
          )}
        </div>
      )}
    </div>
  );
}

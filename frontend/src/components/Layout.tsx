import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  AlertTriangle,
  ClipboardList,
  FileBarChart2,
  Search,
  Building2,
  Users,
  PieChart,
  CalendarClock,
  BarChart3,
  ListChecks,
  FileText,
  Shield,
  Briefcase,
  Brain,
  Activity,
  TrendingDown,
  Zap,
  Bell,
  Settings,
  SearchIcon,
  BookOpen,
} from 'lucide-react';

interface NavItem {
  path: string;
  label: string;
  icon: React.ReactNode;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    title: '홈',
    items: [
      { path: '/', label: '대시보드', icon: <LayoutDashboard size={16} /> },
    ]
  },
  {
    title: '경보 관리',
    items: [
      { path: '/ews-alerts',     label: 'EWS 경보센터',    icon: <AlertTriangle size={16} /> },
      { path: '/ews-action',     label: '경보 액션 관리',  icon: <ClipboardList size={16} /> },
      { path: '/monthly-report', label: '월간 EWS 보고서', icon: <FileBarChart2 size={16} /> },
    ]
  },
  {
    title: '기업/RM 관리',
    items: [
      { path: '/search',       label: '기업 검색',      icon: <Search size={16} /> },
      { path: '/companies',    label: '기업 조회',      icon: <Building2 size={16} /> },
      { path: '/rm-portfolio', label: 'RM 포트폴리오', icon: <Users size={16} /> },
    ]
  },
  {
    title: '여신 포트폴리오',
    items: [
      { path: '/portfolio',         label: '포트폴리오 분석',    icon: <PieChart size={16} /> },
      { path: '/maturity-calendar', label: '만기 도래 캘린더',   icon: <CalendarClock size={16} /> },
      { path: '/concentration',     label: '집중도 한도 관리',   icon: <BarChart3 size={16} /> },
    ]
  },
  {
    title: '리스크 분석',
    items: [
      { path: '/asset-classification', label: '자산건전성',     icon: <ListChecks size={16} /> },
      { path: '/ecl',                  label: 'IFRS9 ECL',    icon: <FileText size={16} /> },
      { path: '/migration-matrix',     label: '등급 전이 행렬', icon: <TrendingDown size={16} /> },
      { path: '/stress-test',          label: '스트레스 테스트', icon: <Zap size={16} /> },
    ]
  },
  {
    title: '여신 운영',
    items: [
      { path: '/covenant', label: '코베넌트',  icon: <Shield size={16} /> },
      { path: '/workout',  label: 'NPL/Workout', icon: <Briefcase size={16} /> },
    ]
  },
  {
    title: '모델/시뮬레이션',
    items: [
      { path: '/model-perf', label: '모델 성능',        icon: <Brain size={16} /> },
      { path: '/simulation', label: '부실탐지 시뮬레이션', icon: <Activity size={16} /> },
    ]
  },
  {
    title: '시스템 문서',
    items: [
      { path: '/system-report', label: '종합 보고서', icon: <BookOpen size={16} /> },
    ]
  },
];

export default function Layout() {
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery('');
    } else {
      navigate('/search');
    }
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* 사이드바 */}
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
        {/* 로고 */}
        <div className="h-16 flex items-center px-4 border-b border-gray-200">
          <Building2 className="text-blue-600 mr-2 shrink-0" size={24} />
          <div>
            <h1 className="text-base font-bold text-gray-900 leading-tight">iM뱅크 EWS</h1>
            <p className="text-xs text-gray-500">기업여신 조기경보</p>
          </div>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 py-3 overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.title} className="mb-3">
              <h3 className="px-4 mb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                {group.title}
              </h3>
              <ul className="space-y-0.5 px-2">
                {group.items.map((item) => (
                  <li key={item.path}>
                    <NavLink
                      to={item.path}
                      end={item.path === '/'}
                      className={({ isActive }) =>
                        `flex items-center px-3 py-1.5 rounded-lg text-xs font-medium transition-colors duration-150 ${
                          isActive
                            ? 'bg-blue-50 text-blue-700'
                            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                        }`
                      }
                    >
                      <span className="mr-2 shrink-0">{item.icon}</span>
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        {/* 하단 */}
        <div className="p-3 border-t border-gray-200">
          <div className="flex items-center text-xs text-gray-500">
            <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
            시스템 정상 운영중
          </div>
          <p className="text-xs text-gray-400 mt-0.5">v2.0.0 | EWS Demo</p>
        </div>
      </aside>

      {/* 메인 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 헤더 */}
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
          <div className="flex items-center space-x-3">
            <h2 className="text-lg font-semibold text-gray-900">기업여신 조기경보 시스템</h2>
            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full font-medium">
              2023-01 ~ 2025-12
            </span>
          </div>

          <div className="flex items-center space-x-3">
            {/* 글로벌 검색 */}
            <form onSubmit={handleSearchSubmit} className="flex items-center">
              <div className="relative">
                <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={15} />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder="기업 검색..."
                  className="pl-9 pr-4 py-1.5 text-sm border border-gray-300 rounded-lg
                             focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent w-44"
                />
              </div>
            </form>

            <button className="relative p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg">
              <Bell size={18} />
              <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-red-500 rounded-full"></span>
            </button>
            <button className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg">
              <Settings size={18} />
            </button>
            <div className="flex items-center">
              <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white text-sm font-medium">
                김
              </div>
              <div className="ml-2">
                <p className="text-sm font-medium text-gray-900">홍길동</p>
                <p className="text-xs text-gray-500">EWS 관리자</p>
              </div>
            </div>
          </div>
        </header>

        {/* 페이지 콘텐츠 */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

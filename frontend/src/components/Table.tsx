import React from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';

interface Column<T> {
  key: string;
  header: string;
  width?: string;
  align?: 'left' | 'center' | 'right';
  render?: (value: any, row: T, index: number) => React.ReactNode;
  sortable?: boolean;
}

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  selectedKey?: string;
  selectedValue?: string | number;
  sortKey?: string;
  sortOrder?: 'asc' | 'desc';
  onSort?: (key: string) => void;
}

export default function Table<T extends Record<string, any>>({
  columns,
  data,
  loading = false,
  emptyMessage = '데이터가 없습니다',
  onRowClick,
  selectedKey,
  selectedValue,
  sortKey,
  sortOrder,
  onSort
}: TableProps<T>) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        {emptyMessage}
      </div>
    );
  }

  const getAlignment = (align?: 'left' | 'center' | 'right') => {
    switch (align) {
      case 'center': return 'text-center';
      case 'right': return 'text-right';
      default: return 'text-left';
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-4 py-3 bg-gray-50 font-semibold text-gray-700 border-b border-gray-200 ${getAlignment(col.align)} ${col.sortable ? 'cursor-pointer hover:bg-gray-100' : ''}`}
                style={{ width: col.width }}
                onClick={() => col.sortable && onSort?.(col.key)}
              >
                <div className={`flex items-center ${col.align === 'right' ? 'justify-end' : col.align === 'center' ? 'justify-center' : ''}`}>
                  {col.header}
                  {col.sortable && sortKey === col.key && (
                    <span className="ml-1">
                      {sortOrder === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => {
            const isSelected = selectedKey && selectedValue && row[selectedKey] === selectedValue;
            return (
              <tr
                key={index}
                className={`border-b border-gray-100 ${onRowClick ? 'cursor-pointer hover:bg-gray-50' : ''} ${isSelected ? 'bg-blue-50' : ''}`}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`px-4 py-3 ${getAlignment(col.align)}`}
                  >
                    {col.render ? col.render(row[col.key], row, index) : row[col.key]}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// 뱃지 컴포넌트
interface BadgeProps {
  children: React.ReactNode;
  variant?: 'success' | 'warning' | 'danger' | 'info' | 'gray';
  size?: 'sm' | 'md';
}

export function Badge({ children, variant = 'gray', size = 'sm' }: BadgeProps) {
  const variantClasses = {
    success: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    danger: 'bg-red-100 text-red-800',
    info: 'bg-blue-100 text-blue-800',
    gray: 'bg-gray-100 text-gray-800',
  };

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  };

  return (
    <span className={`inline-flex items-center rounded-full font-medium ${variantClasses[variant]} ${sizeClasses[size]}`}>
      {children}
    </span>
  );
}

// 셀 포맷터 헬퍼 함수들
export const CellFormatters = {
  amount: (value: number) => (
    <span className="font-mono">{new Intl.NumberFormat('ko-KR').format(value / 1_000_000)}백만</span>
  ),

  amountBillion: (value: number) => (
    <span className="font-mono">{(value / 100_000_000).toFixed(1)}억</span>
  ),

  percent: (value: number, decimals = 2) => (
    <span className="font-mono">{value.toFixed(decimals)}%</span>
  ),

  ratio: (value: number, decimals = 2) => (
    <span className="font-mono">{(value * 100).toFixed(decimals)}%</span>
  ),

  date: (value: string) => {
    if (!value) return '-';
    const date = new Date(value);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  },

  grade: (value: string) => {
    const getColor = (grade: string) => {
      if (!grade) return 'text-gray-600';
      if (grade.startsWith('AAA') || grade.startsWith('AA')) return 'text-blue-700';
      if (grade.startsWith('A')) return 'text-blue-600';
      if (grade.startsWith('BBB')) return 'text-green-600';
      if (grade.startsWith('BB')) return 'text-yellow-600';
      if (grade.startsWith('B')) return 'text-orange-600';
      if (grade.startsWith('C')) return 'text-red-600';
      if (grade === 'D') return 'text-red-800';
      return 'text-gray-600';
    };
    return <span className={`font-semibold ${getColor(value)}`}>{value}</span>;
  },

  status: (value: string) => {
    const variants: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'gray'> = {
      ACTIVE: 'success',
      APPROVED: 'success',
      NORMAL: 'success',
      PASS: 'success',
      PENDING: 'warning',
      REVIEW: 'warning',
      UNDER_REVIEW: 'warning',
      WARNING: 'warning',
      WAIVED: 'warning',
      REJECTED: 'danger',
      CRITICAL: 'danger',
      BREACH: 'danger',
      INACTIVE: 'gray',
      EXPIRED: 'gray',
    };
    return <Badge variant={variants[value?.toUpperCase()] || 'gray'}>{value}</Badge>;
  },
};

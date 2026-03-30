import React from 'react';
import { PieChart, Pie, Cell } from 'recharts';

interface CardProps {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  headerAction?: React.ReactNode;
  noPadding?: boolean;
}

export default function Card({
  title,
  subtitle,
  children,
  className = '',
  headerAction,
  noPadding = false
}: CardProps) {
  return (
    <div className={`bg-white rounded-lg shadow-sm border border-gray-200 ${className}`}>
      {(title || headerAction) && (
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <div>
            {title && <h3 className="text-base font-semibold text-gray-900">{title}</h3>}
            {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
          </div>
          {headerAction && <div>{headerAction}</div>}
        </div>
      )}
      <div className={noPadding ? '' : 'p-4'}>{children}</div>
    </div>
  );
}

// 통계 카드 컴포넌트
interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: React.ReactNode;
  change?: number;
  icon?: React.ReactNode;
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'orange' | 'gray';
}

export function StatCard({ title, value, subtitle, change, icon, color = 'blue' }: StatCardProps) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    orange: 'bg-orange-50 text-orange-600',
    gray: 'bg-gray-50 text-gray-600',
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500 font-medium">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
          {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
          {change !== undefined && (
            <p className={`text-sm mt-1 ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {change >= 0 ? '↑' : '↓'} {Math.abs(change).toFixed(1)}%
            </p>
          )}
        </div>
        {icon && (
          <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

// 반원형 게이지 카드 컴포넌트
interface GaugeCardProps {
  title: string;
  value: number;
  max?: number;
  min?: number;
  unit?: string;
  warning?: number;
  critical?: number;
}

export function GaugeCard({
  title,
  value,
  max = 100,
  min = 0,
  unit = '%',
  warning,
  critical
}: GaugeCardProps) {
  const clampedPct = Math.min(Math.max(((value - min) / (max - min)) * 100, 0), 100);

  let fillColor = '#22c55e'; // green
  let statusLabel = '정상';
  if (critical !== undefined && value >= critical) {
    fillColor = '#ef4444';
    statusLabel = '위험';
  } else if (warning !== undefined && value >= warning) {
    fillColor = '#eab308';
    statusLabel = '주의';
  }

  // 반원 게이지: startAngle=180, endAngle=0 (왼쪽→오른쪽)
  const gaugeData = [
    { value: clampedPct },
    { value: 100 - clampedPct },
  ];

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 flex flex-col">
      <p className="text-sm text-gray-500 font-medium mb-1">{title}</p>

      <div className="flex-1 flex flex-col items-center justify-center">
        <div className="relative" style={{ width: 220, height: 130 }}>
          <PieChart width={220} height={130}>
            {/* 배경 트랙 */}
            <Pie
              data={[{ value: 100 }]}
              cx={110} cy={120}
              startAngle={180} endAngle={0}
              innerRadius={75} outerRadius={105}
              dataKey="value"
              strokeWidth={0}
            >
              <Cell fill="#e5e7eb" />
            </Pie>
            {/* 값 채우기 */}
            <Pie
              data={gaugeData}
              cx={110} cy={120}
              startAngle={180} endAngle={0}
              innerRadius={75} outerRadius={105}
              dataKey="value"
              strokeWidth={0}
            >
              <Cell fill={fillColor} />
              <Cell fill="transparent" />
            </Pie>
          </PieChart>
          {/* 중앙 텍스트 */}
          <div className="absolute inset-0 flex flex-col items-center justify-end pb-3 pointer-events-none">
            <span className="text-3xl font-bold" style={{ color: fillColor, lineHeight: 1 }}>
              {value.toFixed(2)}{unit}
            </span>
            <span className="text-xs font-semibold mt-1" style={{ color: fillColor }}>
              {statusLabel}
            </span>
          </div>
        </div>

        {/* 임계값 레이블 */}
        <div className="flex gap-4 mt-2 text-xs text-gray-400">
          <span>{min}{unit} 정상</span>
          {warning !== undefined && (
            <span className="text-yellow-600 font-medium">주의 {warning}{unit}+</span>
          )}
          {critical !== undefined && (
            <span className="text-red-600 font-medium">위험 {critical}{unit}+</span>
          )}
          <span>{max}{unit}</span>
        </div>
      </div>
    </div>
  );
}

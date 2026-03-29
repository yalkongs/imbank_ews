import React from 'react';

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
  subtitle?: string;
  change?: number;
  icon?: React.ReactNode;
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'gray';
}

export function StatCard({ title, value, subtitle, change, icon, color = 'blue' }: StatCardProps) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
    yellow: 'bg-yellow-50 text-yellow-600',
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

// 게이지 카드 컴포넌트
interface GaugeCardProps {
  title: string;
  value: number;
  max?: number;
  min?: number;
  target?: number;
  unit?: string;
  warning?: number;
  critical?: number;
}

export function GaugeCard({
  title,
  value,
  max = 100,
  min = 0,
  target,
  unit = '%',
  warning,
  critical
}: GaugeCardProps) {
  const percentage = ((value - min) / (max - min)) * 100;
  const targetPercentage = target ? ((target - min) / (max - min)) * 100 : null;

  let barColor = 'bg-green-500';
  if (critical && value >= critical) barColor = 'bg-red-500';
  else if (warning && value >= warning) barColor = 'bg-yellow-500';

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm text-gray-500 font-medium">{title}</p>
        <p className="text-lg font-bold text-gray-900">
          {value.toFixed(2)}{unit}
        </p>
      </div>
      <div className="relative h-3 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`absolute left-0 top-0 h-full ${barColor} rounded-full transition-all duration-500`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
        {targetPercentage && (
          <div
            className="absolute top-0 w-0.5 h-full bg-gray-800"
            style={{ left: `${targetPercentage}%` }}
          />
        )}
      </div>
      <div className="flex justify-between mt-1 text-xs text-gray-400">
        <span>{min}{unit}</span>
        {target && <span className="text-gray-600">목표: {target}{unit}</span>}
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}

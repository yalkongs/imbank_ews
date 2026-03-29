import React from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

// 색상 팔레트
export const COLORS = {
  primary: '#1e40af',
  secondary: '#3b82f6',
  accent: '#06b6d4',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  critical: '#dc2626',
  gray: '#6b7280',
  palette: ['#1e40af', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']
};

// 공통 툴팁 스타일
const tooltipStyle = {
  backgroundColor: 'white',
  border: '1px solid #e5e7eb',
  borderRadius: '8px',
  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
};

interface TrendChartProps {
  data: any[];
  lines: {
    key: string;
    name: string;
    color?: string;
    strokeDasharray?: string;
    yAxisId?: string;
  }[];
  xAxisKey?: string;
  height?: number;
  showLegend?: boolean;
  referenceLines?: { y: number; label: string; color?: string }[];
}

export function TrendChart({
  data,
  lines,
  xAxisKey = 'date',
  height = 300,
  showLegend = true,
  referenceLines = []
}: TrendChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey={xAxisKey}
          tick={{ fontSize: 12 }}
          tickLine={false}
        />
        <YAxis tick={{ fontSize: 12 }} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        {showLegend && <Legend />}

        {referenceLines.map((ref, i) => (
          <ReferenceLine
            key={i}
            y={ref.y}
            label={{ value: ref.label, fontSize: 10 }}
            stroke={ref.color || COLORS.danger}
            strokeDasharray="5 5"
          />
        ))}

        {lines.map((line, i) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.name}
            stroke={line.color || COLORS.palette[i % COLORS.palette.length]}
            strokeWidth={2}
            strokeDasharray={line.strokeDasharray}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

interface AreaChartProps {
  data: any[];
  areas: {
    key: string;
    name: string;
    color?: string;
    stackId?: string;
  }[];
  xAxisKey?: string;
  height?: number;
  showLegend?: boolean;
}

export function StackedAreaChart({
  data,
  areas,
  xAxisKey = 'date',
  height = 300,
  showLegend = true
}: AreaChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={xAxisKey} tick={{ fontSize: 12 }} tickLine={false} />
        <YAxis tick={{ fontSize: 12 }} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        {showLegend && <Legend />}

        {areas.map((area, i) => (
          <Area
            key={area.key}
            type="monotone"
            dataKey={area.key}
            name={area.name}
            stackId={area.stackId || 'stack'}
            fill={area.color || COLORS.palette[i % COLORS.palette.length]}
            stroke={area.color || COLORS.palette[i % COLORS.palette.length]}
            fillOpacity={0.6}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

interface BarChartProps {
  data: any[];
  bars: {
    key: string;
    name: string;
    color?: string;
    stackId?: string;
  }[];
  xAxisKey?: string;
  height?: number;
  showLegend?: boolean;
  layout?: 'horizontal' | 'vertical';
}

export function GroupedBarChart({
  data,
  bars,
  xAxisKey = 'name',
  height = 300,
  showLegend = true,
  layout = 'horizontal'
}: BarChartProps) {
  if (layout === 'vertical') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 80, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis type="number" tick={{ fontSize: 12 }} tickLine={false} />
          <YAxis dataKey={xAxisKey} type="category" tick={{ fontSize: 12 }} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} />
          {showLegend && <Legend />}

          {bars.map((bar, i) => (
            <Bar
              key={bar.key}
              dataKey={bar.key}
              name={bar.name}
              stackId={bar.stackId}
              fill={bar.color || COLORS.palette[i % COLORS.palette.length]}
              radius={[0, 4, 4, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={xAxisKey} tick={{ fontSize: 12 }} tickLine={false} />
        <YAxis tick={{ fontSize: 12 }} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        {showLegend && <Legend />}

        {bars.map((bar, i) => (
          <Bar
            key={bar.key}
            dataKey={bar.key}
            name={bar.name}
            stackId={bar.stackId}
            fill={bar.color || COLORS.palette[i % COLORS.palette.length]}
            radius={[4, 4, 0, 0]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

interface DonutChartProps {
  data: { name: string; value: number; color?: string }[];
  height?: number;
  innerRadius?: number;
  outerRadius?: number;
  centerText?: string;
  centerValue?: string;
}

export function DonutChart({
  data,
  height = 250,
  innerRadius = 60,
  outerRadius = 100,
  centerText,
  centerValue
}: DonutChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={innerRadius}
          outerRadius={outerRadius}
          paddingAngle={2}
          dataKey="value"
        >
          {data.map((entry, index) => (
            <Cell key={index} fill={entry.color || COLORS.palette[index % COLORS.palette.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} />
        <Legend
          formatter={(value) => (
            <span style={{ color: '#374151', fontSize: 12 }}>{value}</span>
          )}
        />

        {/* 중앙 텍스트 */}
        {(centerText || centerValue) && (
          <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle">
            {centerValue && (
              <tspan x="50%" dy="-0.5em" fontSize="24" fontWeight="bold" fill="#1f2937">
                {centerValue}
              </tspan>
            )}
            {centerText && (
              <tspan x="50%" dy="1.5em" fontSize="12" fill="#6b7280">
                {centerText}
              </tspan>
            )}
          </text>
        )}
      </PieChart>
    </ResponsiveContainer>
  );
}

// 미니 스파크라인 차트
interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}

export function Sparkline({ data, width = 100, height = 30, color = COLORS.primary }: SparklineProps) {
  const chartData = data.map((value, index) => ({ value, index }));

  return (
    <ResponsiveContainer width={width} height={height}>
      <LineChart data={chartData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// 게이지 차트 (반원형)
interface GaugeChartProps {
  value: number;
  min?: number;
  max?: number;
  target?: number;
  warning?: number;
  critical?: number;
  label?: string;
  size?: number;
}

export function GaugeChart({
  value,
  min = 0,
  max = 100,
  warning,
  critical,
  label,
  size = 200
}: GaugeChartProps) {
  const percentage = Math.min(Math.max((value - min) / (max - min) * 100, 0), 100);

  // 색상 결정
  let color = COLORS.success;
  if (critical && value >= critical) color = COLORS.danger;
  else if (warning && value >= warning) color = COLORS.warning;

  const data = [
    { name: 'value', value: percentage },
    { name: 'remaining', value: 100 - percentage }
  ];

  return (
    <div className="relative" style={{ width: size, height: size / 2 + 20 }}>
      <ResponsiveContainer width="100%" height={size / 2 + 20}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="100%"
            startAngle={180}
            endAngle={0}
            innerRadius={(size / 2) * 0.6}
            outerRadius={(size / 2) * 0.85}
            paddingAngle={0}
            dataKey="value"
          >
            <Cell fill={color} />
            <Cell fill="#e5e7eb" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-end pb-2">
        <span className="text-2xl font-bold" style={{ color }}>{value.toFixed(1)}%</span>
        {label && <span className="text-xs text-gray-500">{label}</span>}
      </div>
    </div>
  );
}

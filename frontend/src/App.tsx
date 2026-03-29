import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Layout } from './components';
import {
  Dashboard,
  EWSAlerts,
  CompanyBrowser,
  Portfolio,
  AssetClassification,
  ECLManagement,
  Covenant,
  Workout,
  ModelPerf,
  Simulation,
  Search,
  EWSAction,
  MonthlyReport,
  MaturityCalendar,
  ConcentrationLimit,
  MigrationMatrix,
  StressTest,
  RMPortfolio,
  SystemReport,
} from './pages';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="ews-alerts" element={<EWSAlerts />} />
        <Route path="companies" element={<CompanyBrowser />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="asset-classification" element={<AssetClassification />} />
        <Route path="ecl" element={<ECLManagement />} />
        <Route path="covenant" element={<Covenant />} />
        <Route path="workout" element={<Workout />} />
        <Route path="model-perf" element={<ModelPerf />} />
        <Route path="simulation" element={<Simulation />} />
        {/* 신규 페이지 */}
        <Route path="search" element={<Search />} />
        <Route path="ews-action" element={<EWSAction />} />
        <Route path="monthly-report" element={<MonthlyReport />} />
        <Route path="maturity-calendar" element={<MaturityCalendar />} />
        <Route path="concentration" element={<ConcentrationLimit />} />
        <Route path="migration-matrix" element={<MigrationMatrix />} />
        <Route path="stress-test" element={<StressTest />} />
        <Route path="rm-portfolio" element={<RMPortfolio />} />
        <Route path="system-report" element={<SystemReport />} />
      </Route>
    </Routes>
  );
}

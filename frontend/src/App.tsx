import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AppProvider } from './store/AppContext';
import { LandingPage } from './pages/LandingPage';
import { OverviewPage } from './pages/OverviewPage';
import { ReconciliationPage } from './pages/ReconciliationPage';
import { ExceptionsPage } from './pages/ExceptionsPage';
import { CopilotPage } from './pages/CopilotPage';
import { RunReportsPage } from './pages/RunReportsPage';
import { SettingsPage } from './pages/SettingsPage';

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Storytelling Landing Page */}
          <Route path="/" element={<LandingPage />} />

          {/* Existing CashUP Product Dashboard under /app */}
          <Route
            path="/app"
            element={
              <Layout>
                <OverviewPage />
              </Layout>
            }
          />
          <Route
            path="/app/reconciliation"
            element={
              <Layout>
                <ReconciliationPage />
              </Layout>
            }
          />
          <Route
            path="/app/exceptions"
            element={
              <Layout>
                <ExceptionsPage />
              </Layout>
            }
          />
          <Route
            path="/app/copilot"
            element={
              <Layout>
                <CopilotPage />
              </Layout>
            }
          />
          <Route
            path="/app/reports"
            element={
              <Layout>
                <RunReportsPage />
              </Layout>
            }
          />
          <Route
            path="/app/settings"
            element={
              <Layout>
                <SettingsPage />
              </Layout>
            }
          />

          {/* Direct legacy route redirects to /app/* */}
          <Route path="/reconciliation" element={<Navigate to="/app/reconciliation" replace />} />
          <Route path="/exceptions" element={<Navigate to="/app/exceptions" replace />} />
          <Route path="/copilot" element={<Navigate to="/app/copilot" replace />} />
          <Route path="/reports" element={<Navigate to="/app/reports" replace />} />
          <Route path="/settings" element={<Navigate to="/app/settings" replace />} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}

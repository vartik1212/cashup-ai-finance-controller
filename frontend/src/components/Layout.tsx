// CashUP — Application Layout Shell

import React, { useEffect, useState, useRef } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, GitMerge, AlertTriangle, MessageSquare, FileBarChart2,
  Settings, Activity, Wifi, WifiOff, Zap,
  Database, PanelLeft, PanelLeftClose, ChevronRight, UploadCloud,
} from 'lucide-react';
import { useApp } from '../store/AppContext';
import { CSVUploadModal } from './ui/CSVUploadModal';
import { LiveSessionClock } from './ui/LiveSessionClock';
import { DatasetSwitchModal } from './ui/DatasetSwitchModal';
import { AgentWorkflowModal } from './ui/AgentWorkflowModal';
import { SpatialFinanceCanvas } from './ui/SpatialFinanceCanvas';

const NAV_ITEMS = [
  { path: '/app', icon: LayoutDashboard, label: 'Overview' },
  { path: '/app/reconciliation', icon: GitMerge, label: 'Reconciliation' },
  { path: '/app/exceptions', icon: AlertTriangle, label: 'Exceptions' },
  { path: '/app/copilot', icon: MessageSquare, label: 'AI Copilot' },
  { path: '/app/reports', icon: FileBarChart2, label: 'Run Reports' },
];

interface SidebarProps {
  isPinned: boolean;
  isHovered: boolean;
  isRefreshing: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onTogglePin: () => void;
  onClose: () => void;
  onCashUpClick: () => void;
}

function Sidebar({
  isPinned,
  isHovered,
  isRefreshing,
  onMouseEnter,
  onMouseLeave,
  onTogglePin,
  onClose,
  onCashUpClick,
}: SidebarProps) {
  const { dataStatus, aiAvailable, aiStatus, currentRun } = useApp();
  const isAiConnected = !!(aiStatus?.available ?? aiAvailable);
  const isOpen = isPinned || isHovered;

  return (
    <>
      {/* Subtle backdrop blur overlay when unpinned and open */}
      {!isPinned && isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-slate-950/40 backdrop-blur-[2px] z-40 transition-opacity duration-300 pointer-events-auto"
        />
      )}

      <aside
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        className={`${
          isPinned
            ? 'w-60 flex-shrink-0 relative z-20'
            : 'fixed top-0 bottom-0 left-0 z-50 w-64'
        } bg-slate-900/95 backdrop-blur-xl border-r border-slate-700/80 shadow-[16px_0_40px_rgba(0,0,0,0.75)] flex flex-col h-full transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${
          !isPinned && !isOpen ? '-translate-x-full pointer-events-none' : 'translate-x-0 pointer-events-auto'
        }`}
      >
        {/* Brand & Pin Action */}
        <div className="px-4 py-4 border-b border-slate-700/60 flex items-center justify-between">
          <button
            onClick={onCashUpClick}
            title="CashUP — Return to home & upload new dataset"
            className="flex items-center gap-2.5 group cursor-pointer text-left rounded-lg p-1 -m-1 hover:bg-slate-800/70 transition-colors"
          >
            <div className="w-7 h-7 bg-cyan-500/20 border border-cyan-500/40 rounded flex items-center justify-center flex-shrink-0 group-hover:border-cyan-400/80 group-hover:bg-cyan-500/30 transition-all">
              <GitMerge size={14} className="text-cyan-400" />
            </div>
            <div>
              <div className="text-sm font-bold text-slate-100 tracking-tight leading-none flex items-center gap-1.5">
                <span className="group-hover:text-cyan-300 transition-colors">CashUP</span>
                {isRefreshing && (
                  <span className="text-[9px] text-cyan-400 font-mono animate-pulse">refreshing…</span>
                )}
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5 leading-none">AI Finance Controller</div>
            </div>
          </button>

          {/* Pin/Unpin Toggle button */}
          <button
            onClick={onTogglePin}
            title={isPinned ? 'Unpin sidebar (Auto-hide on leave)' : 'Pin sidebar open'}
            className={`p-1.5 rounded-lg border transition-colors cursor-pointer flex items-center justify-center ${
              isPinned
                ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300'
                : 'border-slate-800 text-slate-500 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            {isPinned ? <PanelLeftClose size={14} /> : <PanelLeft size={14} />}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(({ path, icon: Icon, label }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/app'}
              onClick={() => {
                if (!isPinned) onClose();
              }}
              className={({ isActive }) =>
                `relative flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200 group ${
                  isActive
                    ? 'bg-cyan-500/8 text-cyan-300 border border-cyan-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <div className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-cyan-400 shadow-[0_0_4px_#22d3ee]" />
                  )}
                  <Icon
                    size={15}
                    className={isActive ? 'text-cyan-400' : 'text-slate-500 group-hover:text-slate-300 transition-colors'}
                  />
                  <span className="font-medium">{label}</span>
                  {path === '/app/exceptions' && currentRun && (currentRun.open_exception_count ?? (currentRun.unresolved + currentRun.human_review)) > 0 && (
                    <span className="ml-auto px-1.5 py-0.5 text-[10px] font-mono font-semibold bg-red-500/20 text-red-400 border border-red-500/30 rounded">
                      {currentRun.open_exception_count ?? (currentRun.unresolved + currentRun.human_review)}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Bottom status */}
        <div className="px-4 py-4 border-t border-slate-700/60 space-y-3">
          {/* System status */}
          <div className="flex items-center gap-2">
            <div className={`w-1.5 h-1.5 rounded-full ${dataStatus ? 'bg-emerald-400' : 'bg-red-400'}`} />
            <span className="text-[11px] text-slate-500">
              {dataStatus?.data_loaded ? 'Data loaded' : 'No data'}
            </span>
            <span className="ml-auto">
              {isAiConnected ? (
                <Wifi size={12} className="text-emerald-400" />
              ) : (
                <WifiOff size={12} className="text-slate-600" />
              )}
            </span>
          </div>

          {/* AI status: quiet, secondary */}
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isAiConnected ? 'bg-emerald-400' : 'bg-slate-600'}`} />
            <span>{isAiConnected ? 'Gemini connected' : 'Data-only mode'}</span>
          </div>

          <NavLink
            to="/app/settings"
            onClick={() => {
              if (!isPinned) onClose();
            }}
            className="flex items-center gap-2 text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
          >
            <Settings size={12} />
            Settings
          </NavLink>
        </div>
      </aside>
    </>
  );
}

function Topbar({
  onToggleSidebar,
  isSidebarPinned,
  onCashUpClick,
  isRefreshing,
}: {
  onToggleSidebar?: () => void;
  isSidebarPinned?: boolean;
  onCashUpClick?: () => void;
  isRefreshing?: boolean;
}) {
  const { currentRun, dataStatus, runStatus, runReconciliation, loadDemo, setUploadModalOpen } = useApp();
  const [switchAction, setSwitchAction] = useState<'demo' | 'upload' | null>(null);
  const isRunning = runStatus === 'running';
  const isLoading = runStatus === 'loading';
  const isBenchmark = Boolean(dataStatus?.has_ground_truth && dataStatus?.dataset_source === 'benchmark');

  const handleDemoClick = () => {
    if (currentRun) {
      setSwitchAction('demo');
    } else {
      loadDemo();
    }
  };

  const handleUploadClick = () => {
    if (currentRun) {
      setSwitchAction('upload');
    } else {
      setUploadModalOpen(true);
    }
  };

  const handleConfirmSwitch = () => {
    if (switchAction === 'demo') {
      loadDemo();
    } else if (switchAction === 'upload') {
      setUploadModalOpen(true);
    }
    setSwitchAction(null);
  };

  return (
    <header className="min-h-[56px] py-2 px-4 sm:px-6 flex-shrink-0 bg-slate-900/90 backdrop-blur-md border-b border-slate-800/80 w-full flex justify-center">
      <div className="w-full max-w-[1560px] flex items-center justify-between gap-3 sm:gap-4 min-w-0">
        {/* Left side: Navigation toggle (if unpinned) + Brand + Run ID + Dataset badge */}
        <div className="flex items-center gap-2.5 sm:gap-3 flex-shrink-0 min-w-0">
          {!isSidebarPinned && (
            <button
              onClick={onToggleSidebar}
              className="p-1.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-800/60 hover:bg-slate-800 text-slate-400 hover:text-cyan-300 transition-colors cursor-pointer flex items-center justify-center flex-shrink-0"
              title="Toggle navigation panel"
            >
              <PanelLeft size={15} />
            </button>
          )}

          {/* CashUP Brand */}
          <button
            onClick={onCashUpClick}
            title="CashUP — Return to home & upload new dataset"
            className="flex items-center px-1.5 py-1 -my-1 rounded-lg hover:bg-slate-800/60 transition-all group cursor-pointer"
          >
            <span className="text-sm font-bold text-slate-100 tracking-tight leading-none group-hover:text-cyan-400 transition-colors">
              CashUP
            </span>
            {isRefreshing && (
              <span className="text-[9px] text-cyan-400 font-mono animate-pulse ml-1.5 hidden sm:inline">
                refreshing…
              </span>
            )}
          </button>

          <div className="hidden sm:block w-px h-3.5 bg-slate-800 flex-shrink-0" />

          {/* Run ID */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-400 font-medium hidden sm:inline">
              Run:
            </span>
            {currentRun ? (
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-800/80 text-cyan-300 border border-slate-700/60 font-semibold tracking-wide">
                {currentRun.run_id}
              </span>
            ) : (
              <span className="text-xs text-slate-600 font-mono">None</span>
            )}
          </div>

          {/* Dataset source badge */}
          <div
            title={isBenchmark ? 'Synthetic benchmark dataset with ground-truth evaluation' : `User uploaded financial CSV dataset (${dataStatus?.dataset_id || 'Active'})`}
            className={`hidden sm:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-medium border cursor-help transition-all whitespace-nowrap ${
              isBenchmark
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/25'
                : 'bg-indigo-500/10 text-indigo-300 border-indigo-500/25'
            }`}
          >
            <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isBenchmark ? 'bg-emerald-400' : 'bg-indigo-400'}`} />
            <span>{isBenchmark ? 'Benchmark Dataset' : 'Uploaded Dataset'}</span>
          </div>
        </div>

        {/* Center: Quiet, unboxed Source Counters */}
        <div className="hidden md:flex items-center gap-3.5 text-xs font-mono text-slate-400">
          <div className="flex items-baseline gap-1.5">
            <span className="text-[10px] text-slate-500 uppercase font-medium">INV</span>
            <span className="text-slate-200 font-semibold tabular-nums">{dataStatus?.invoices ?? 0}</span>
          </div>
          <span className="text-slate-700">·</span>
          <div className="flex items-baseline gap-1.5">
            <span className="text-[10px] text-slate-500 uppercase font-medium">SET</span>
            <span className="text-slate-200 font-semibold tabular-nums">{dataStatus?.settlements ?? 0}</span>
          </div>
          <span className="text-slate-700">·</span>
          <div className="flex items-baseline gap-1.5">
            <span className="text-[10px] text-slate-500 uppercase font-medium">BNK</span>
            <span className="text-slate-200 font-semibold tabular-nums">{dataStatus?.bank_transactions ?? 0}</span>
          </div>
          {(dataStatus?.refunds ?? 0) > 0 && (
            <>
              <span className="text-slate-700">·</span>
              <div className="flex items-baseline gap-1.5">
                <span className="text-[10px] text-slate-500 uppercase font-medium">RFD</span>
                <span className="text-slate-200 font-semibold tabular-nums">{dataStatus?.refunds ?? 0}</span>
              </div>
            </>
          )}
        </div>

        {/* Right side: Live Session Clock + Demo / Upload + Run CTA */}
        <div className="flex items-center gap-2 sm:gap-2.5 flex-shrink-0 ml-auto">
          <LiveSessionClock />

          <div className="w-px h-3.5 bg-slate-800 flex-shrink-0" />

          {/* Load demo */}
          <button
            onClick={handleDemoClick}
            disabled={isLoading || isRunning}
            title="Load benchmark synthetic dataset with ground truth"
            className="flex items-center gap-1 px-2.5 sm:px-3 py-1.5 text-xs text-slate-300 border border-slate-700/80 rounded-lg hover:border-slate-600 hover:text-white transition-colors disabled:opacity-40 flex-shrink-0 cursor-pointer"
          >
            <Database size={12} />
            <span>Demo</span>
          </button>

          {/* Upload Data */}
          <button
            onClick={handleUploadClick}
            disabled={isLoading || isRunning}
            title="Upload multiple CSV files (Invoices, Settlements, Bank Statements, Refunds)"
            className="flex items-center gap-1 px-2.5 sm:px-3 py-1.5 text-xs text-indigo-300 bg-indigo-500/10 border border-indigo-500/30 rounded-lg hover:bg-indigo-500/20 hover:border-indigo-500/50 transition-colors disabled:opacity-40 font-medium flex-shrink-0 cursor-pointer"
          >
            <UploadCloud size={13} />
            <span>Upload</span>
          </button>

          {/* Run reconciliation (Primary CTA - strongest item) */}
          <button
            onClick={runReconciliation}
            disabled={isRunning || isLoading || (dataStatus?.invoices ?? 0) === 0}
            className={`flex items-center gap-1.5 px-3.5 sm:px-4 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-sm flex-shrink-0 whitespace-nowrap ${
              isRunning
                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 cursor-wait'
                : 'bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-white shadow-cyan-900/20 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer'
            }`}
          >
            <Zap size={12} className={isRunning ? 'animate-pulse' : ''} />
            <span>{isRunning ? 'Running…' : 'Run Reconciliation'}</span>
          </button>
        </div>

        <DatasetSwitchModal
          isOpen={Boolean(switchAction)}
          onClose={() => setSwitchAction(null)}
          onConfirm={handleConfirmSwitch}
        />
      </div>
    </header>
  );
}

function DataSourcePill({ label, count }: { label: string; count: number }) {
  const active = count > 0;
  return (
    <div className={`flex items-center gap-1.5 px-2 py-1 rounded border ${
      active ? 'border-slate-600/60 text-slate-400' : 'border-slate-700/40 text-slate-600'
    }`}>
      <div className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-emerald-400' : 'bg-slate-600'}`} />
      <span className="font-mono font-medium text-[11px]">{label}</span>
      <span className="text-[11px]">{count}</span>
    </div>
  );
}

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const navigate = useNavigate();
  const {
    refreshDataStatus, loadLatestRun, runStatus,
    currentTrace, isWorkflowModalOpen, setWorkflowModalOpen, currentRun,
    isUploadModalOpen, setUploadModalOpen, resetWorkspace,
  } = useApp();

  const [isSidebarPinned, setIsSidebarPinned] = useState<boolean>(() => {
    try {
      return (localStorage.getItem('cashup_sidebar_pinned') ?? localStorage.getItem('reconai_sidebar_pinned')) === 'true';
    } catch {
      return false;
    }
  });
  const [isSidebarHovered, setIsSidebarHovered] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    refreshDataStatus();
    loadLatestRun();
  }, []);

  const handleCashUpClick = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    // 1. Navigate to main app overview page
    navigate('/app');
    // 2. Clear active run & reset workspace state
    resetWorkspace();
    // 3. Refresh data status from backend
    try {
      await refreshDataStatus();
    } catch (err) {
      console.error('Failed to refresh data:', err);
    }
    // 4. Open CSV upload modal so user can upload new files immediately
    setUploadModalOpen(true);
    // 5. Close unpinned sidebar if open
    setIsSidebarHovered(false);
    setTimeout(() => {
      setIsRefreshing(false);
    }, 600);
  };

  const handleMouseEnter = () => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
      hoverTimeoutRef.current = null;
    }
    setIsSidebarHovered(true);
  };

  const handleMouseLeave = () => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    hoverTimeoutRef.current = setTimeout(() => {
      setIsSidebarHovered(false);
    }, 220); // 220ms smooth grace exit period
  };

  const togglePin = () => {
    setIsSidebarPinned(prev => {
      const next = !prev;
      try {
        localStorage.setItem('cashup_sidebar_pinned', String(next));
      } catch {}
      return next;
    });
  };

  return (
    <div className="relative flex h-screen w-full max-w-full bg-slate-950 text-slate-100 overflow-hidden">
      {/* Ambient Spatial Finance Canvas */}
      <SpatialFinanceCanvas />

      {/* Left Edge Hover Trigger Zone (Active when unpinned) */}
      {!isSidebarPinned && (
        <>
          <div
            onMouseEnter={handleMouseEnter}
            className="fixed left-0 top-0 bottom-0 w-4 z-40 cursor-pointer pointer-events-auto"
            title="Hover left edge to reveal navigation"
          />

          {/* Floating Subtle Peek Tab on Left Edge */}
          <div
            onMouseEnter={handleMouseEnter}
            onClick={() => setIsSidebarHovered(true)}
            className={`fixed left-0 top-1/2 -translate-y-1/2 z-40 flex items-center justify-center py-3.5 px-1 rounded-r-lg bg-slate-900/90 hover:bg-slate-800 border border-l-0 border-slate-700/80 shadow-[0_0_15px_rgba(6,182,212,0.15)] text-slate-400 hover:text-cyan-400 transition-all duration-300 cursor-pointer group ${
              isSidebarHovered ? 'opacity-0 pointer-events-none -translate-x-full' : 'opacity-100 translate-x-0'
            }`}
            title="Hover or click to open sidebar"
          >
            <ChevronRight size={13} className="group-hover:translate-x-0.5 transition-transform text-cyan-400/80" />
          </div>
        </>
      )}

      {/* Foreground Interactive Shell */}
      <div className="relative z-10 flex h-full w-full max-w-full overflow-hidden">
        <Sidebar
          isPinned={isSidebarPinned}
          isHovered={isSidebarHovered}
          isRefreshing={isRefreshing}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          onTogglePin={togglePin}
          onClose={() => setIsSidebarHovered(false)}
          onCashUpClick={handleCashUpClick}
        />
        <div className="flex-1 flex flex-col min-w-0 max-w-full bg-slate-950/40 backdrop-blur-[2px] overflow-hidden items-center">
          <Topbar
            onToggleSidebar={() => setIsSidebarHovered(prev => !prev)}
            isSidebarPinned={isSidebarPinned}
            onCashUpClick={handleCashUpClick}
            isRefreshing={isRefreshing}
          />
          <main className="flex-1 overflow-y-auto overflow-x-hidden min-w-0 w-full flex flex-col items-center">
            <div className="w-full max-w-[1560px] flex-1 flex flex-col min-w-0">
              {children}
            </div>
          </main>
        </div>
      </div>

      <AgentWorkflowModal
        isOpen={isWorkflowModalOpen}
        onClose={() => setWorkflowModalOpen(false)}
        isRunning={runStatus === 'running'}
        trace={currentTrace}
        runId={currentRun?.run_id}
      />

      <CSVUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        onSuccess={async () => {
          resetWorkspace();
          await refreshDataStatus();
          await loadLatestRun();
        }}
      />
    </div>
  );
}


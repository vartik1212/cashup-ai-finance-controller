// Page 4 — AI Finance Copilot
// Grounded in the current reconciliation run with real-time HUD and interactive invoice drill-down

import React, { useState, useRef, useEffect } from 'react';
import {
  Send, Sparkles, WifiOff, ChevronRight, Bot, User,
  FileSpreadsheet, AlertTriangle, ShieldCheck, Activity,
  ExternalLink, ArrowRight
} from 'lucide-react';
import type { ChatMessage, ReconciliationResult } from '../types';
import { useApp } from '../store/AppContext';
import * as api from '../api/client';
import { formatCurrency, formatPct } from '../utils/format';
import { EvidencePanel } from '../components/ui/EvidencePanel';

const SUGGESTED_QUERIES = [
  'Summarize this reconciliation run.',
  'How many exceptions are unresolved?',
  'What is the unresolved amount?',
  'Which exceptions should I review first?',
  'Show the highest value exceptions.',
  'Why is BILL-2026057 unresolved?',
  'Show duplicate transactions.',
  'Which settlements were delayed?',
  'What percentage was auto-verified?',
  'What are the biggest financial risks in this run?',
];

function MessageBubble({
  message,
  onSelectInvoice,
}: {
  message: ChatMessage;
  onSelectInvoice?: (id: string) => void;
}) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`w-7 h-7 rounded flex items-center justify-center flex-shrink-0 mt-0.5 ${
          isUser
            ? 'bg-slate-700 text-slate-400'
            : 'bg-cyan-500/20 border border-cyan-500/30 text-cyan-400'
        }`}
      >
        {isUser ? <User size={13} /> : <Bot size={13} />}
      </div>

      <div className={`flex-1 max-w-[85%] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1.5`}>
        <div
          className={`px-4 py-3 rounded-lg text-xs md:text-sm leading-relaxed ${
            isUser
              ? 'bg-slate-700/60 text-slate-200 border border-slate-600/40'
              : 'bg-slate-800/60 text-slate-200 border border-slate-700/50'
          }`}
        >
          {/* Render markdown-like structured content */}
          {message.content.split('\n').map((line, i) => {
            if (line.startsWith('**') && line.endsWith('**')) {
              return (
                <div key={i} className="font-semibold text-slate-100 mb-1">
                  {line.slice(2, -2)}
                </div>
              );
            }
            if (line.startsWith('- ')) {
              return (
                <div key={i} className="flex items-start gap-2 my-0.5">
                  <ChevronRight size={11} className="text-cyan-500 mt-1 flex-shrink-0" />
                  <span
                    dangerouslySetInnerHTML={{
                      __html: line
                        .slice(2)
                        .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-slate-100 font-semibold">$1</strong>'),
                    }}
                  />
                </div>
              );
            }
            return line ? (
              <div
                key={i}
                className="my-0.5"
                dangerouslySetInnerHTML={{
                  __html: line.replace(
                    /\*\*([^*]+)\*\*/g,
                    '<strong class="text-slate-100 font-semibold">$1</strong>'
                  ),
                }}
              />
            ) : (
              <div key={i} className="h-1.5" />
            );
          })}
        </div>

        {/* Clickable Referenced Invoices */}
        {message.referenced_ids && message.referenced_ids.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 px-1">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">Referenced:</span>
            {message.referenced_ids.map(id => (
              <button
                key={id}
                onClick={() => onSelectInvoice?.(id)}
                className="group flex items-center gap-1 text-[11px] font-mono bg-slate-800/90 hover:bg-cyan-950 border border-slate-700 hover:border-cyan-500/50 text-cyan-400 hover:text-cyan-300 px-2 py-0.5 rounded transition-all shadow-sm"
                title={`Inspect evidence for ${id}`}
              >
                <span>{id}</span>
                <ExternalLink size={10} className="opacity-60 group-hover:opacity-100" />
              </button>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between w-full text-[10px] text-slate-500 px-1 pt-0.5">
          <div>
            {!isUser && (
              message.mode === 'connected' ? (
                <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                  <Sparkles size={10} /> AI Copilot: Gemini Connected
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-slate-500 font-medium">
                  <WifiOff size={10} /> AI Copilot: Data-only mode
                </span>
              )
            )}
          </div>
          <div>
            {new Date(message.timestamp).toLocaleTimeString('en-IN', {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export function CopilotPage() {
  const {
    currentRun,
    aiAvailable,
    aiStatus,
    results,
    exceptions,
    selectedResult,
    selectResult,
    handleReview,
  } = useApp();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  // Invalidate previous Copilot conversation & context when active run_id changes or is cleared
  useEffect(() => {
    setMessages([]);
    setInput('');
  }, [currentRun?.run_id]);

  const handleSelectInvoice = async (invoiceId: string) => {
    // Check in existing loaded results/exceptions first
    const match =
      results.find(r => r.invoice_id === invoiceId) ||
      exceptions.find(r => r.invoice_id === invoiceId);

    if (match) {
      selectResult(match);
      return;
    }

    // Otherwise fetch directly from backend
    try {
      const fetched = await api.fetchResultByInvoice(invoiceId, currentRun?.run_id);
      if (fetched) {
        selectResult(fetched);
      }
    } catch {
      // Ignored if not found
    }
  };

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await api.sendCopilotMessage({
        message: text.trim(),
        run_id: currentRun?.run_id,
        conversation_history: messages,
      });

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
        referenced_ids: response.referenced_ids,
        mode: response.mode || (response.ai_available ? 'connected' : 'data_only'),
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch {
      const errMsg: ChatMessage = {
        role: 'assistant',
        content:
          'Unable to connect to the Copilot backend. Please ensure the backend server is running.',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const isGeminiActive = aiStatus?.available ?? aiAvailable;

  return (
    <div className="flex h-full w-full overflow-hidden">
      {/* Main Copilot Content */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <div className="px-6 py-3.5 border-b border-slate-700/60 flex items-center justify-between flex-shrink-0 bg-slate-900/50">
          <div>
            <div className="flex items-center gap-2.5 mb-0.5">
              <Sparkles size={16} className="text-cyan-400" />
              <h1 className="text-sm font-semibold text-slate-100">Finance Operations Copilot</h1>
            </div>
            <p className="text-xs text-slate-500">
              Deterministic ground-truth intelligence powered by CashUP & Gemini.
            </p>
          </div>
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded border text-xs font-medium ${
              isGeminiActive
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                : 'bg-slate-800 border-slate-700 text-slate-400'
            }`}
          >
            {isGeminiActive ? (
              <>
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <Sparkles size={11} />
                <span>AI Copilot: Gemini Connected</span>
              </>
            ) : (
              <>
                <WifiOff size={11} />
                <span>AI Copilot: Data-only mode</span>
              </>
            )}
          </div>
        </div>

        {/* Current Run Context Strip (HUD) */}
        <div className="px-6 py-2.5 bg-slate-800/30 border-b border-slate-700/50 flex items-center justify-between gap-4 text-xs flex-shrink-0 overflow-x-auto">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-1.5">
              <FileSpreadsheet size={13} className="text-slate-400" />
              <span className="text-slate-500">Run:</span>
              <span className="font-mono text-slate-200 font-medium">
                {currentRun?.run_id || 'No active run'}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <Activity size={13} className="text-cyan-400" />
              <span className="text-slate-500">Processed:</span>
              <span className="font-mono text-slate-200 font-medium">
                {currentRun?.records_processed ?? 0}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <ShieldCheck size={13} className="text-emerald-400" />
              <span className="text-slate-500">Match Rate:</span>
              <span className="font-mono text-emerald-400 font-semibold">
                {currentRun ? formatPct(currentRun.match_rate) : '0.0%'}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <AlertTriangle size={13} className="text-amber-400" />
              <span className="text-slate-500">Open Exceptions:</span>
              <span className="font-mono text-amber-400 font-semibold">
                {currentRun?.open_exception_count ?? 0}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500">Unresolved Amt:</span>
              <span className="font-mono text-red-400 font-medium">
                {formatCurrency(currentRun?.unresolved_amount ?? 0)}
              </span>
            </div>
          </div>
          <div className="text-[11px] text-slate-500 whitespace-nowrap">
            {isGeminiActive ? 'Grounded with Gemini' : 'Rule-Grounded Engine'}
          </div>
        </div>

        {/* Conversation Area */}
        <div className="flex-1 overflow-auto px-6 py-5 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-10 max-w-2xl mx-auto text-center">
              <div className="w-12 h-12 bg-cyan-500/10 border border-cyan-500/20 rounded-xl flex items-center justify-center mb-4 shadow-lg shadow-cyan-950/20">
                <Sparkles size={22} className="text-cyan-400" />
              </div>
              <h2 className="text-base font-semibold text-slate-200 mb-1">
                CashUP Finance Copilot
              </h2>
              <p className="text-xs text-slate-400 max-w-md mb-6 leading-relaxed">
                Query current run reconciliation metrics, investigate unresolved exceptions, inspect
                delayed settlements, and prioritize ledger investigations.
              </p>

              {/* Suggested Questions Grid */}
              <div className="w-full space-y-2 text-left">
                <div className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mb-2 text-center">
                  Recommended Finance Inquiries
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {SUGGESTED_QUERIES.map(q => (
                    <button
                      key={q}
                      onClick={() => sendMessage(q)}
                      disabled={!currentRun || isLoading}
                      className="flex items-center justify-between p-3 bg-slate-800/40 hover:bg-slate-800/80 border border-slate-700/50 hover:border-cyan-500/40 rounded-lg text-xs text-slate-300 hover:text-cyan-200 transition-all text-left group disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <span className="line-clamp-1">{q}</span>
                      <ChevronRight
                        size={13}
                        className="text-slate-600 group-hover:text-cyan-400 group-hover:translate-x-0.5 transition-all flex-shrink-0 ml-2"
                      />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble
              key={i}
              message={msg}
              onSelectInvoice={handleSelectInvoice}
            />
          ))}

          {isLoading && (
            <div className="flex gap-3">
              <div className="w-7 h-7 rounded bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center">
                <Bot size={13} className="text-cyan-400" />
              </div>
              <div className="px-4 py-3 bg-slate-800/60 border border-slate-700/50 rounded-lg flex items-center gap-2">
                <div className="flex gap-1">
                  {[0, 1, 2].map(i => (
                    <div
                      key={i}
                      className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"
                      style={{ animationDelay: `${i * 150}ms` }}
                    />
                  ))}
                </div>
                <span className="text-xs text-slate-400 ml-1">
                  Querying reconciliation state & reasoning...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggested Queries Chips Strip when messages exist */}
        {messages.length > 0 && (
          <div className="px-6 py-2 border-t border-slate-800 bg-slate-900/40 flex gap-2 overflow-x-auto flex-shrink-0">
            {SUGGESTED_QUERIES.slice(0, 5).map(q => (
              <button
                key={q}
                onClick={() => sendMessage(q)}
                disabled={isLoading}
                className="text-[11px] whitespace-nowrap px-2.5 py-1 bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/50 hover:border-cyan-500/30 rounded text-slate-400 hover:text-slate-200 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input Area */}
        <div className="px-6 py-4 border-t border-slate-700/60 bg-slate-900/70 flex-shrink-0">
          {!isGeminiActive && (
            <div className="flex items-center gap-2 mb-2.5 px-3 py-1.5 bg-slate-800/50 border border-slate-700/50 rounded text-[11px] text-slate-400">
              <WifiOff size={11} className="text-amber-400" />
              <span>
                Gemini API key not configured — operating in deterministic Data-only mode.
              </span>
            </div>
          )}
          <div className="flex gap-3">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
              placeholder={
                currentRun
                  ? 'Ask about reconciliation results, exceptions, or specific invoices (e.g., BILL-2026057)…'
                  : 'Load a reconciliation run first to chat…'
              }
              disabled={!currentRun || isLoading}
              className="flex-1 px-4 py-2.5 bg-slate-800/70 border border-slate-700 hover:border-slate-600 focus:border-cyan-500 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none transition-all disabled:opacity-40"
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isLoading || !currentRun}
              className="px-4 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg text-white font-medium text-xs flex items-center gap-2 transition-all shadow-md shadow-cyan-900/20"
            >
              <span>Send</span>
              <Send size={13} />
            </button>
          </div>
        </div>
      </div>

      {/* Slide-in Evidence Panel on Clicking Referenced Invoices */}
      {selectedResult && (
        <EvidencePanel
          result={selectedResult}
          onClose={() => selectResult(null)}
          onApprove={id => handleReview(id, 'approve')}
          onReject={id => handleReview(id, 'reject')}
          onKeep={id => handleReview(id, 'keep_open')}
        />
      )}
    </div>
  );
}

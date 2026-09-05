// CashUP — Dataset Switch Confirmation Modal
import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AlertCircle, ArrowRight, X } from 'lucide-react';

interface DatasetSwitchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  targetActionName?: string;
}

export function DatasetSwitchModal({
  isOpen,
  onClose,
  onConfirm,
}: DatasetSwitchModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const content = (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="switch-dataset-title"
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 bg-slate-950/80 backdrop-blur-sm overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-[480px] bg-slate-900 border border-slate-700/90 rounded-2xl shadow-2xl p-6 sm:p-7 space-y-6 animate-in fade-in zoom-in-95 duration-150 my-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header with icon and title */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 flex-shrink-0 mt-0.5">
              <AlertCircle size={22} />
            </div>
            <div>
              <h3
                id="switch-dataset-title"
                className="text-base sm:text-lg font-semibold text-slate-100 leading-snug"
              >
                Switch active dataset?
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Active workspace transition
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition -mr-1 -mt-1"
            aria-label="Close dialog"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body content with concise clean copy */}
        <div className="p-4 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-1.5">
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed font-normal">
            Uploading a new dataset will replace the current active workspace.
          </p>
          <p className="text-xs text-slate-400 leading-relaxed font-normal">
            Your existing run will remain available in Run Reports.
          </p>
        </div>

        {/* Actions aligned cleanly at the bottom */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800/90">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl transition cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              onConfirm();
              onClose();
            }}
            className="px-4 py-2 text-xs font-semibold text-white bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 rounded-xl flex items-center gap-1.5 shadow-lg shadow-cyan-950/50 transition cursor-pointer"
          >
            <span>Switch Dataset</span>
            <ArrowRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );

  return typeof document !== 'undefined' ? createPortal(content, document.body) : content;
}

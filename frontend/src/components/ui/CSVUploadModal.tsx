// CashUP — CSV Ingestion & Schema Mapping Modal
// Production-quality multi-file upload, profiling, column mapping & validation wizard.

import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  X,
  Check,
  HelpCircle,
  Layers,
  Database,
  RefreshCw,
} from 'lucide-react';
import { uploadAndProfile, confirmUpload } from '../../api/client';
import type {
  FileProfile,
  CanonicalFieldDef,
  ValidationSummary,
} from '../../types';

interface CSVUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface FileValidationIssue {
  fileIndex: number;
  filename: string;
  fileType: string;
  field: string;
  fieldLabel: string;
  message: string;
}

interface ValidationReport {
  isValid: boolean;
  readyFilesCount: number;
  attentionFilesCount: number;
  fileIssues: Record<number, FileValidationIssue[]>;
  allIssues: FileValidationIssue[];
  firstBlockingIssue?: FileValidationIssue;
}

export const CSVUploadModal: React.FC<CSVUploadModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [step, setStep] = useState<'upload' | 'inspect' | 'map' | 'validate'>('upload');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [profiles, setProfiles] = useState<FileProfile[]>([]);
  const [availableSchemas, setAvailableSchemas] = useState<Record<string, CanonicalFieldDef[]>>({});
  const [activeFileIndex, setActiveFileIndex] = useState<number>(0);

  // User confirmed mappings: fileIndex -> { sourceCol: targetField }
  const [fileMappings, setFileMappings] = useState<Record<number, Record<string, string>>>({});
  // User confirmed file types: fileIndex -> fileType
  const [fileTypes, setFileTypes] = useState<Record<number, string>>({});

  const [validationSummaries, setValidationSummaries] = useState<ValidationSummary[]>([]);
  const [datasetCounts, setDatasetCounts] = useState<{
    existing: { invoices: number; settlements: number; bank_transactions: number; refunds?: number };
    added: { invoices: number; settlements: number; bank_transactions: number; refunds?: number };
    result: { invoices: number; settlements: number; bank_transactions: number; refunds?: number };
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // UX & Validation state
  const [highlightedField, setHighlightedField] = useState<string | null>(null);
  const [validationAttempted, setValidationAttempted] = useState(false);
  const isIngestingRef = useRef(false);

  // Purely derived from current classifications: NEVER cached independently
  const hasInvoiceSource = profiles.length > 0 && profiles.some(
    (p, idx) => (fileTypes[idx] || p.detected_file_type) === 'INVOICES'
  );

  const computeValidationReport = (
    mappingsOverride?: Record<number, Record<string, string>>
  ): ValidationReport => {
    const mapsToUse = mappingsOverride || fileMappings;
    const fileIssues: Record<number, FileValidationIssue[]> = {};
    const allIssues: FileValidationIssue[] = [];

    profiles.forEach((p, idx) => {
      fileIssues[idx] = [];
      const activeType = fileTypes[idx] || p.detected_file_type;
      const schemaFields = availableSchemas[activeType] || p.canonical_schema || [];
      const currentFileMap = mapsToUse[idx] || {};
      const mappedFields = new Set(Object.values(currentFileMap));

      if (activeType === 'UNKNOWN') {
        const issue: FileValidationIssue = {
          fileIndex: idx,
          filename: p.filename,
          fileType: 'UNKNOWN',
          field: '__file_type__',
          fieldLabel: 'File Classification',
          message: 'File classification is UNKNOWN. Select a valid financial type.',
        };
        fileIssues[idx].push(issue);
        allIssues.push(issue);
      }

      // Check all required canonical schema fields
      schemaFields.forEach(f => {
        if (f.required && !mappedFields.has(f.field)) {
          const issue: FileValidationIssue = {
            fileIndex: idx,
            filename: p.filename,
            fileType: activeType,
            field: f.field,
            fieldLabel: f.label,
            message: `Missing required mapping: ${f.label}`,
          };
          fileIssues[idx].push(issue);
          allIssues.push(issue);
        }
      });
    });

    const readyFilesCount = profiles.filter((_, idx) => (fileIssues[idx] || []).length === 0).length;
    const attentionFilesCount = profiles.length - readyFilesCount;

    return {
      isValid: allIssues.length === 0,
      readyFilesCount,
      attentionFilesCount,
      fileIssues,
      allIssues,
      firstBlockingIssue: allIssues[0],
    };
  };

  React.useEffect(() => {
    if (isOpen) {
      setStep('upload');
      setSelectedFiles([]);
      setProfiles([]);
      setAvailableSchemas({});
      setActiveFileIndex(0);
      setFileMappings({});
      setFileTypes({});
      setValidationSummaries([]);
      setDatasetCounts(null);
      setError(null);
      setIsLoading(false);
      setHighlightedField(null);
      setValidationAttempted(false);
      isIngestingRef.current = false;
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      const csvs = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.csv'));
      if (csvs.length === 0) {
        setError('Only CSV files (.csv) are supported.');
        return;
      }
      setSelectedFiles(csvs);
      setError(null);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const csvs = Array.from(e.target.files).filter(f => f.name.toLowerCase().endsWith('.csv'));
      setSelectedFiles(csvs);
      setError(null);
    }
  };

  const clearAllFiles = () => {
    setSelectedFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (idx: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== idx));
  };

  // Step 1 -> Step 2: Upload & Profile
  const handleStartProfiling = async () => {
    if (selectedFiles.length === 0) {
      setError('Please select at least one CSV file.');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const res = await uploadAndProfile(selectedFiles);
      setProfiles(res.profiles);
      setAvailableSchemas(res.available_schemas || {});

      // Initialize default mappings and file types
      const initialMaps: Record<number, Record<string, string>> = {};
      const initialTypes: Record<number, string> = {};
      res.profiles.forEach((p: FileProfile, idx: number) => {
        initialTypes[idx] = p.detected_file_type;
        initialMaps[idx] = {};
        p.column_mappings.forEach(m => {
          if (m.target_field) {
            initialMaps[idx][m.source_column] = m.target_field;
          }
        });
      });
      setFileMappings(initialMaps);
      setFileTypes(initialTypes);
      setActiveFileIndex(0);
      setStep('inspect');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Profiling failed.');
    } finally {
      setIsLoading(false);
    }
  };

  // Helper to suggest the best source column for a canonical field
  const getCandidateForField = (
    profile: FileProfile,
    targetField: string,
    currentMap: Record<string, string>,
    schema: CanonicalFieldDef[]
  ): string | null => {
    let bestCol: string | null = null;
    let bestScore = -1;

    const normTarget = targetField.toLowerCase().replace(/[^a-z0-9]/g, '_');

    profile.columns.forEach(col => {
      const currentAssigned = currentMap[col.column_name];
      const isAssignedToOtherRequired =
        currentAssigned &&
        currentAssigned !== 'IGNORE_COLUMN' &&
        currentAssigned !== targetField &&
        schema.some(f => f.field === currentAssigned && f.required);

      // Skip columns already assigned to another required field
      if (isAssignedToOtherRequired) return;

      let score = 0;
      const normCol = col.column_name.toLowerCase().replace(/[^a-z0-9]/g, '_');
      const detectedType = col.detected_type || 'text';

      // 1. Exact or strong synonym matching
      if (normCol === normTarget) score += 100;

      if (
        targetField === 'invoice_id' ||
        targetField === 'settlement_id' ||
        targetField === 'bank_transaction_id' ||
        targetField === 'refund_id'
      ) {
        if (
          [
            'doc_ref',
            'doc_no',
            'doc_number',
            'ref_no',
            'bill_no',
            'bill_number',
            'invoice_no',
            'invoice_number',
            'inv_no',
            'inv_id',
            'payout_key',
            'payout_id',
            'txn_id',
            'transaction_id',
            'refund_id',
            'credit_note_no',
          ].some(k => normCol.includes(k))
        )
          score += 75;
        else if (['ref', 'id', 'key', 'number', 'no', 'code'].some(k => normCol.includes(k)))
          score += 40;
        if (detectedType === 'id_string') score += 30;
        else if (detectedType === 'text') score += 10;
        if (
          detectedType === 'date' ||
          detectedType === 'datetime' ||
          detectedType === 'currency' ||
          detectedType === 'number'
        )
          score -= 60;
      } else if (
        targetField === 'invoice_date' ||
        targetField === 'settlement_date' ||
        targetField === 'transaction_date' ||
        targetField === 'refund_date'
      ) {
        if (
          [
            'raised_on',
            'issued_on',
            'invoice_date',
            'inv_date',
            'bill_date',
            'created_at',
            'created_date',
            'processed_at',
            'settled_at',
            'txn_date',
            'value_dt',
            'value_date',
            'posting_date',
          ].some(k => normCol.includes(k))
        )
          score += 75;
        else if (['date', 'dt', 'raised', 'issued', 'created', 'processed', 'on'].some(k => normCol.includes(k)))
          score += 40;
        if (detectedType === 'date' || detectedType === 'datetime') score += 40;
        if (detectedType === 'currency' || detectedType === 'number') score -= 60;
      } else if (
        targetField === 'amount' ||
        targetField === 'gross_amount' ||
        targetField === 'credit_amount' ||
        targetField === 'refund_amount' ||
        targetField === 'net_amount'
      ) {
        if (
          [
            'gross_due',
            'amount_due',
            'invoice_amount',
            'bill_value',
            'total_amount',
            'captured_amount',
            'deposit',
            'credit_amount',
            'refund_amount',
            'amount_remitted',
            'original_value',
          ].some(k => normCol.includes(k))
        )
          score += 75;
        else if (['amount', 'gross', 'due', 'total', 'amt', 'value', 'deposit', 'credit'].some(k => normCol.includes(k)))
          score += 40;
        if (detectedType === 'currency') score += 40;
        else if (detectedType === 'number') score += 30;
      } else if (targetField === 'customer_name' || targetField === 'description') {
        if (['party', 'customer', 'client', 'buyer', 'account', 'narrative', 'narration', 'particulars'].some(k => normCol.includes(k)))
          score += 65;
        if (detectedType === 'text') score += 20;
      }

      if (!currentAssigned || currentAssigned === 'IGNORE_COLUMN') score += 15;

      if (score > bestScore) {
        bestScore = score;
        bestCol = col.column_name;
      }
    });

    return bestScore > 0 ? bestCol : null;
  };

  const getAutoFixedMappings = (targetFileIdx?: number) => {
    const next: Record<number, Record<string, string>> = {};
    profiles.forEach((_, i) => {
      next[i] = { ...(fileMappings[i] || {}) };
    });

    const indicesToFix = targetFileIdx !== undefined ? [targetFileIdx] : profiles.map((_, i) => i);

    indicesToFix.forEach(idx => {
      const p = profiles[idx];
      if (!p) return;
      const currentType = fileTypes[idx] || p.detected_file_type;
      const schema = availableSchemas[currentType] || p.canonical_schema || [];
      const fileMap = { ...(next[idx] || {}) };

      schema.filter(f => f.required).forEach(req => {
        const currentOwner = Object.keys(fileMap).find(k => fileMap[k] === req.field);
        if (!currentOwner) {
          const candidate = getCandidateForField(p, req.field, fileMap, schema);
          if (candidate) {
            fileMap[candidate] = req.field;
          }
        }
      });

      next[idx] = fileMap;
    });

    return next;
  };

  const handleAutoFixMappings = (targetFileIdx?: number) => {
    const fixed = getAutoFixedMappings(targetFileIdx);
    setFileMappings(fixed);
    setHighlightedField(null);
    setError(null);
  };

  const handleFileTypeChange = (fileIdx: number, newType: string) => {
    setFileTypes(prev => ({ ...prev, [fileIdx]: newType }));
    setError(null);

    const p = profiles[fileIdx];
    if (p) {
      const schema = availableSchemas[newType] || p.canonical_schema || [];
      const newFileMap: Record<string, string> = {};

      schema.forEach(fieldDef => {
        const candidate = getCandidateForField(p, fieldDef.field, newFileMap, schema);
        if (candidate) {
          newFileMap[candidate] = fieldDef.field;
        }
      });

      setFileMappings(prev => ({ ...prev, [fileIdx]: newFileMap }));
    }
  };

  // Step 3: Handle manual mapping change
  const handleMappingChange = (fileIdx: number, sourceCol: string, targetField: string) => {
    setFileMappings(prev => {
      const fileMap = { ...(prev[fileIdx] || {}) };
      if (targetField === 'IGNORE_COLUMN') {
        delete fileMap[sourceCol];
      } else {
        fileMap[sourceCol] = targetField;
      }
      return { ...prev, [fileIdx]: fileMap };
    });
    setHighlightedField(null);
    setError(null);
  };

  // Step 3 -> Step 4: Validate and Confirm
  const handleConfirmAndValidate = async () => {
    if (isLoading || isIngestingRef.current) {
      return; // Double-submit protection
    }
    isIngestingRef.current = true;
    setIsLoading(true);
    setError(null);
    setValidationAttempted(true);

    try {
      // 1. Validate ALL uploaded files and ALL required canonical mappings
      let report = computeValidationReport();
      let activeMappings = fileMappings;

      if (!report.isValid) {
        // Attempt intelligent auto-fix for missing required mappings
        const autoFixed = getAutoFixedMappings();
        const autoReport = computeValidationReport(autoFixed);
        if (autoReport.isValid) {
          setFileMappings(autoFixed);
          activeMappings = autoFixed;
          report = autoReport;
        }
      }

      if (!report.isValid) {
        const firstIssue = report.firstBlockingIssue!;
        // Switch/focus to the FIRST file containing a blocking error
        setActiveFileIndex(firstIssue.fileIndex);
        setHighlightedField(firstIssue.field);
        setError(`${firstIssue.filename}: ${firstIssue.message}`);
        setTimeout(() => {
          const el = document.getElementById(`required-field-${firstIssue.field}`) || document.getElementById('validation-error-summary');
          el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
        return;
      }

      const payloadFiles = profiles.map((p, idx) => ({
        filename: p.filename,
        file_type: fileTypes[idx] || p.detected_file_type,
        column_mapping: activeMappings[idx] || {},
        file_content_b64: p.file_content_b64,
      }));

      const res = await confirmUpload({ files: payloadFiles });
      setValidationSummaries(res.summaries);
      if (res.dataset_counts) {
        setDatasetCounts(res.dataset_counts);
      }
      setStep('validate');
    } catch (err: any) {
      const rawDetail = err?.response?.data?.detail;
      const rawMsg = typeof rawDetail === 'string' ? rawDetail : (err?.message || 'Server error occurred during ingestion.');
      const safeMsg = `Validation failed: ${rawMsg}`;
      setError(safeMsg);
      setTimeout(() => {
        const el = document.getElementById('validation-error-summary') || document.getElementById('general-error-banner');
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
    } finally {
      setIsLoading(false);
      isIngestingRef.current = false;
    }
  };

  const handleFinalReconcile = () => {
    onSuccess();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <UploadCloud size={20} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                Import Financial Data
                <span className="text-[10px] px-2 py-0.5 rounded-full font-mono font-medium bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                  CSV Ingestion
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Upload varying schemas with deterministic column detection & AI-assisted mapping
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-300 p-1.5 rounded-lg hover:bg-slate-800 transition"
          >
            <X size={18} />
          </button>
        </div>

        {/* Wizard Progress Bar */}
        <div className="px-6 py-3 bg-slate-950/50 border-b border-slate-800 flex items-center justify-between text-xs">
          <div className={`flex items-center gap-2 ${step === 'upload' ? 'text-indigo-400 font-semibold' : 'text-slate-400'}`}>
            <span className="w-5 h-5 rounded-full border flex items-center justify-center text-[10px]">1</span>
            <span>Upload CSVs</span>
          </div>
          <ArrowRight size={12} className="text-slate-600" />
          <div className={`flex items-center gap-2 ${step === 'inspect' ? 'text-indigo-400 font-semibold' : 'text-slate-400'}`}>
            <span className="w-5 h-5 rounded-full border flex items-center justify-center text-[10px]">2</span>
            <span>Inspect & Type</span>
          </div>
          <ArrowRight size={12} className="text-slate-600" />
          <div className={`flex items-center gap-2 ${step === 'map' ? 'text-indigo-400 font-semibold' : 'text-slate-400'}`}>
            <span className="w-5 h-5 rounded-full border flex items-center justify-center text-[10px]">3</span>
            <span>Schema Mapping</span>
          </div>
          <ArrowRight size={12} className="text-slate-600" />
          <div className={`flex items-center gap-2 ${step === 'validate' ? 'text-emerald-400 font-semibold' : 'text-slate-400'}`}>
            <span className="w-5 h-5 rounded-full border flex items-center justify-center text-[10px]">4</span>
            <span>Validation</span>
          </div>
        </div>

        {/* Body Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {error && step !== 'map' && (
            <div id="general-error-banner" className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-400 text-xs flex items-start gap-2">
              <AlertTriangle size={15} className="mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* STEP 1: UPLOAD */}
          {step === 'upload' && (
            <div className="space-y-4">
              <div
                onDragOver={e => e.preventDefault()}
                onDrop={handleFileDrop}
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-700 hover:border-indigo-500/60 rounded-xl p-8 text-center cursor-pointer transition bg-slate-950/30 hover:bg-slate-800/30"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".csv"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <UploadCloud size={40} className="mx-auto text-indigo-400 mb-3" />
                <div className="text-sm font-medium text-slate-200">
                  Drop financial CSV files here or <span className="text-indigo-400 underline">browse</span>
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Supports multiple CSVs: Invoices, Settlements, Bank Statements, Refunds (Max 10MB each)
                </div>
              </div>

              {selectedFiles.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Selected Files ({selectedFiles.length})
                    </div>
                    <button
                      type="button"
                      onClick={clearAllFiles}
                      className="text-[11px] text-slate-400 hover:text-rose-400 transition"
                    >
                      Clear all
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {selectedFiles.map((file, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2.5 bg-slate-800/60 border border-slate-700/60 rounded-lg text-xs"
                      >
                        <div className="flex items-center gap-2 truncate">
                          <FileText size={16} className="text-indigo-400 flex-shrink-0" />
                          <span className="font-medium text-slate-200 truncate">{file.name}</span>
                          <span className="text-[10px] text-slate-500">({(file.size / 1024).toFixed(1)} KB)</span>
                        </div>
                        <button
                          onClick={e => {
                            e.stopPropagation();
                            removeFile(idx);
                          }}
                          className="text-slate-500 hover:text-rose-400 p-1 rounded transition"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 2: INSPECT & PROFILING */}
          {step === 'inspect' && (
            <div className="space-y-4">
              <div className="text-xs text-slate-400">
                Files successfully analyzed. Review detected classifications before confirming column mappings:
              </div>
              <div className="grid grid-cols-1 gap-3">
                {profiles.map((p, idx) => {
                  const currentType = fileTypes[idx] || p.detected_file_type;
                  return (
                    <div
                      key={idx}
                      className="p-4 bg-slate-950/40 border border-slate-700/60 rounded-xl space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <FileText size={18} className="text-indigo-400" />
                          <span className="text-sm font-semibold text-slate-100">{p.filename}</span>
                          <span className="text-xs text-slate-500 font-mono">
                            {p.row_count} rows • {p.column_count} columns
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] text-slate-400">File Type:</span>
                          <select
                            value={currentType}
                            onChange={e => handleFileTypeChange(idx, e.target.value)}
                            className="bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-slate-200 font-medium focus:outline-none focus:border-indigo-400"
                          >
                            <option value="INVOICES">INVOICES</option>
                            <option value="SETTLEMENTS">SETTLEMENTS</option>
                            <option value="BANK_TRANSACTIONS">BANK_TRANSACTIONS</option>
                            <option value="REFUNDS">REFUNDS</option>
                            <option value="UNKNOWN">UNKNOWN</option>
                          </select>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 text-xs text-slate-400 bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                        <div className="flex items-center gap-1.5">
                          <span className="text-slate-500">Confidence:</span>
                          <span className="font-semibold text-cyan-400 font-mono">
                            {(p.detection_confidence * 100).toFixed(0)}%
                          </span>
                          <span className="text-[10px] text-slate-500">({p.detection_source})</span>
                        </div>
                        <div className="w-px h-3 bg-slate-700" />
                        <div className="text-[11px] text-slate-400 truncate flex-1">
                          {p.detection_reason}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* STEP 3: SCHEMA MAPPING */}
          {step === 'map' && profiles.length > 0 && (() => {
            const validationReport = computeValidationReport();
            const activeProfile = profiles[activeFileIndex] || profiles[0];
            const activeType = fileTypes[activeFileIndex] || activeProfile.detected_file_type;
            const schemaFields = availableSchemas[activeType] || activeProfile.canonical_schema || [];
            const currentFileMap = fileMappings[activeFileIndex] || {};
            const missingRequiredFields = schemaFields
              .filter(f => f.required)
              .filter(f => !Object.values(currentFileMap).includes(f.field));

            return (
              <div className="space-y-4">
                {/* Validation Summary when attention is required */}
                {(!validationReport.isValid && (validationAttempted || Boolean(error))) && (
                  <div
                    id="validation-error-summary"
                    className="p-3.5 bg-rose-500/10 border border-rose-500/40 rounded-xl space-y-2.5 animate-in fade-in duration-150"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-rose-300 font-semibold text-xs">
                        <AlertCircle size={16} className="text-rose-400 flex-shrink-0" />
                        <span>
                          {validationReport.readyFilesCount} {validationReport.readyFilesCount === 1 ? 'file' : 'files'} ready • {validationReport.attentionFilesCount} {validationReport.attentionFilesCount === 1 ? 'file requires' : 'files require'} attention
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleAutoFixMappings(activeFileIndex)}
                        className="flex items-center gap-1.5 px-3 py-1 bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white text-xs font-semibold rounded-lg shadow-md transition cursor-pointer"
                        title="Automatically assign matching columns for all missing required fields"
                      >
                        <Sparkles size={13} className="text-amber-300" />
                        Auto-Fix Mappings
                      </button>
                    </div>
                    {validationReport.firstBlockingIssue && (
                      <div className="text-xs text-rose-200 pl-6 space-y-0.5 border-t border-rose-500/20 pt-2">
                        <div className="font-mono text-[11px] text-rose-300 font-bold">
                          {validationReport.firstBlockingIssue.filename}
                        </div>
                        <div className="text-slate-300">
                          Missing required mapping: <strong className="text-rose-200 underline decoration-rose-400/50">{validationReport.firstBlockingIssue.fieldLabel}</strong>
                        </div>
                      </div>
                    )}
                    {error && (!validationReport.firstBlockingIssue || !error.includes(validationReport.firstBlockingIssue.message)) && (
                      <div className="text-xs text-rose-300 pl-6 pt-1 font-mono">
                        {error}
                      </div>
                    )}
                  </div>
                )}

                {/* Derived invoice source guard warning */}
                {!hasInvoiceSource && (
                  <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-300 text-xs flex items-center gap-2">
                    <AlertTriangle size={15} className="text-amber-400 flex-shrink-0" />
                    <span>No invoice source detected. Review file classifications before ingestion.</span>
                  </div>
                )}

                {/* File selector tabs with status indicator */}
                {profiles.length > 1 && (
                  <div className="flex gap-2 border-b border-slate-800 pb-2 overflow-x-auto">
                    {profiles.map((p, idx) => {
                      const currentType = fileTypes[idx] || p.detected_file_type;
                      const fileIssuesList = validationReport.fileIssues[idx] || [];
                      const hasIssues = fileIssuesList.length > 0;

                      return (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => {
                            setActiveFileIndex(idx);
                            setHighlightedField(null);
                          }}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-2 whitespace-nowrap ${
                            activeFileIndex === idx
                              ? 'bg-indigo-600 text-white shadow-md'
                              : 'bg-slate-800/60 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                          }`}
                        >
                          <span className="font-semibold">{currentType}</span>
                          {hasIssues ? (
                            <span className="inline-flex items-center gap-0.5 text-[10px] font-bold text-amber-300 bg-amber-500/25 border border-amber-500/40 px-1.5 py-0.5 rounded-full">
                              ⚠ {fileIssuesList.length}
                            </span>
                          ) : (
                            <span className="inline-flex items-center text-[10px] font-bold text-emerald-400 bg-emerald-500/20 border border-emerald-500/40 px-1.5 py-0.5 rounded-full">
                              ✓ Ready
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Active File Mapping Header */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <div className="flex items-center gap-2">
                      <span>
                        Map columns for <strong className="text-slate-200">{activeProfile.filename}</strong>:
                      </span>
                      <select
                        value={activeType}
                        onChange={e => handleFileTypeChange(activeFileIndex, e.target.value)}
                        className="bg-slate-800 border border-slate-600 rounded px-2 py-0.5 text-xs text-slate-200 font-medium focus:outline-none focus:border-indigo-400"
                      >
                        <option value="INVOICES">INVOICES</option>
                        <option value="SETTLEMENTS">SETTLEMENTS</option>
                        <option value="BANK_TRANSACTIONS">BANK_TRANSACTIONS</option>
                        <option value="REFUNDS">REFUNDS</option>
                        <option value="UNKNOWN">UNKNOWN</option>
                      </select>
                    </div>
                    <div className="flex items-center gap-3">
                      {missingRequiredFields.length > 0 && (
                        <button
                          type="button"
                          onClick={() => handleAutoFixMappings(activeFileIndex)}
                          className="flex items-center gap-1 text-[11px] font-medium text-indigo-300 hover:text-indigo-200 transition"
                        >
                          <Sparkles size={12} className="text-amber-300" />
                          Auto-Fix This File
                        </button>
                      )}
                      <span className="text-[11px] text-slate-500">
                        * Required canonical fields
                      </span>
                    </div>
                  </div>

                  <div className="border border-slate-700/80 rounded-lg overflow-hidden bg-slate-950/40">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-800/70 text-slate-300 font-semibold border-b border-slate-700">
                          <th className="p-2.5">Source Column / Field</th>
                          <th className="p-2.5">Sample Values</th>
                          <th className="p-2.5">CashUP Canonical Field</th>
                          <th className="p-2.5 text-right">Status / Confidence</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {/* Highlighted Missing Required Canonical Fields */}
                        {missingRequiredFields.map(reqField => {
                          const suggestedCol = getCandidateForField(
                            activeProfile,
                            reqField.field,
                            currentFileMap,
                            schemaFields
                          );
                          return (
                            <tr
                              key={`missing-${reqField.field}`}
                              id={`required-field-${reqField.field}`}
                              className={`border-b transition-all duration-200 ${
                                highlightedField === reqField.field
                                  ? 'bg-rose-950/70 border-rose-500 ring-2 ring-rose-500/80'
                                  : 'bg-rose-950/30 border-rose-900/50'
                              }`}
                            >
                              <td className="p-2.5">
                                <div className="font-semibold text-rose-200 flex items-center gap-1.5">
                                  <AlertTriangle size={14} className="text-rose-400 flex-shrink-0" />
                                  <span>{reqField.label} <span className="text-rose-400 font-bold">*</span></span>
                                </div>
                                <div className="text-[10px] text-rose-400/80 font-medium">
                                  Required canonical field
                                </div>
                              </td>
                              <td className="p-2.5">
                                <div className="text-[11px] text-slate-400 italic">
                                  {suggestedCol ? (
                                    <span className="text-indigo-300 font-mono not-italic">
                                      Suggested: <strong className="text-white">{suggestedCol}</strong>
                                    </span>
                                  ) : (
                                    'Not assigned to any source column'
                                  )}
                                </div>
                              </td>
                              <td className="p-2.5">
                                <div className="flex items-center gap-1.5">
                                  <select
                                    value=""
                                    onChange={e => {
                                      if (e.target.value) {
                                        handleMappingChange(activeFileIndex, e.target.value, reqField.field);
                                        setHighlightedField(null);
                                        setError(null);
                                      }
                                    }}
                                    className="w-full bg-slate-900 border border-rose-500/70 rounded px-2 py-1 text-xs text-rose-200 focus:outline-none focus:border-rose-400 font-medium"
                                  >
                                    <option value="">— Assign source column for {reqField.label} —</option>
                                    {activeProfile.columns.map(c => (
                                      <option key={c.column_name} value={c.column_name}>
                                        {c.column_name} ({c.detected_type})
                                      </option>
                                    ))}
                                  </select>
                                  {suggestedCol && (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        handleMappingChange(activeFileIndex, suggestedCol, reqField.field);
                                        setHighlightedField(null);
                                        setError(null);
                                      }}
                                      className="px-2 py-1 bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white text-[11px] font-semibold rounded whitespace-nowrap transition shadow cursor-pointer"
                                      title={`Assign ${suggestedCol} to ${reqField.label}`}
                                    >
                                      Assign
                                    </button>
                                  )}
                                </div>
                              </td>
                              <td className="p-2.5 text-right font-mono">
                                <div className="flex flex-col items-end gap-0.5">
                                  <span className="text-[11px] font-bold text-rose-400">
                                    Required field "{reqField.label}" is not mapped.
                                  </span>
                                </div>
                              </td>
                            </tr>
                          );
                        })}

                        {/* Existing Source Column Rows */}
                        {activeProfile.columns.map((col, cIdx) => {
                          const rawSelectedField = currentFileMap[col.column_name] || '';
                          const isFieldInSchema = schemaFields.some(f => f.field === rawSelectedField);
                          const selectedField = isFieldInSchema ? rawSelectedField : '';
                          const isIgnored = !selectedField || selectedField === 'IGNORE_COLUMN';
                          const isHighlighted = highlightedField && selectedField === highlightedField;

                          const mapItem = activeProfile.column_mappings.find(
                            m => m.source_column === col.column_name
                          );
                          const conf = isIgnored ? 0 : (mapItem?.confidence ?? 0);
                          const band = isIgnored ? 'LOW' : (mapItem?.confidence_band || (conf >= 0.85 ? 'HIGH' : conf >= 0.60 ? 'MED' : 'LOW'));

                          return (
                            <tr
                              key={cIdx}
                              id={`col-field-${col.column_name}`}
                              className={`hover:bg-slate-800/30 transition ${
                                isHighlighted ? 'bg-rose-950/40 ring-1 ring-rose-500/80' : ''
                              }`}
                            >
                              <td className="p-2.5">
                                <div className="font-medium text-slate-200">{col.column_name}</div>
                                <div className="text-[10px] text-slate-500">
                                  type: {col.detected_type} • nulls: {col.null_percentage}%
                                </div>
                              </td>
                              <td className="p-2.5">
                                <div className="text-[11px] text-slate-400 font-mono truncate max-w-xs">
                                  {col.sample_values.join(', ') || '—'}
                                </div>
                              </td>
                              <td className="p-2.5">
                                <select
                                  value={selectedField || 'IGNORE_COLUMN'}
                                  onChange={e =>
                                    handleMappingChange(
                                      activeFileIndex,
                                      col.column_name,
                                      e.target.value
                                    )
                                  }
                                  className={`w-full bg-slate-900 border rounded px-2 py-1 text-xs focus:outline-none transition ${
                                    selectedField
                                      ? 'border-indigo-500/60 text-slate-100 font-medium'
                                      : 'border-slate-700 text-slate-400'
                                  }`}
                                >
                                  <option value="IGNORE_COLUMN">— Ignore Column —</option>
                                  {schemaFields.map(f => (
                                    <option key={f.field} value={f.field}>
                                      {f.label} {f.required ? '*' : ''}
                                    </option>
                                  ))}
                                </select>
                              </td>
                              <td className="p-2.5 text-right font-mono">
                                {!isIgnored && conf > 0 ? (
                                  <div className="flex flex-col items-end gap-0.5">
                                    <span
                                      className={`text-[11px] font-semibold ${
                                        conf >= 0.85
                                          ? 'text-emerald-400'
                                          : conf >= 0.60
                                          ? 'text-amber-400'
                                          : 'text-rose-400'
                                      }`}
                                    >
                                      {(conf * 100).toFixed(0)}% ({band})
                                    </span>
                                    {mapItem?.reason && (
                                      <span className="text-[9px] text-slate-500 truncate max-w-[140px]" title={mapItem.reason}>
                                        {mapItem.reason}
                                      </span>
                                    )}
                                  </div>
                                ) : (
                                  <span className="text-[10px] text-slate-600">Ignored</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* STEP 4: VALIDATION REPORT */}
          {step === 'validate' && (
            <div className="space-y-4">
              <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-center gap-3">
                <CheckCircle2 size={24} className="text-emerald-400 flex-shrink-0" />
                <div>
                  <div className="text-sm font-semibold text-emerald-300">
                    Dataset Validated & Updated Successfully
                  </div>
                  <div className="text-xs text-slate-400">
                    Records have been incrementally normalized and added to the active dataset.
                  </div>
                </div>
              </div>

              {/* Dataset Counts: Existing -> Adding -> Result */}
              {datasetCounts && (
                <div className="grid grid-cols-3 gap-3 p-4 bg-slate-950/60 border border-slate-700/60 rounded-xl text-xs">
                  <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-2 flex items-center gap-1.5">
                      <Database size={13} className="text-slate-400" />
                      Existing Dataset
                    </div>
                    <div className="space-y-1 font-mono text-slate-300">
                      <div>{datasetCounts.existing.invoices} invoices</div>
                      <div>{datasetCounts.existing.settlements} settlements</div>
                      <div>{datasetCounts.existing.bank_transactions} bank transactions</div>
                      {(datasetCounts.existing.refunds ?? 0) > 0 && (
                        <div>{datasetCounts.existing.refunds} refunds</div>
                      )}
                    </div>
                  </div>
                  <div className="p-3 bg-indigo-950/30 rounded-lg border border-indigo-500/20">
                    <div className="text-[10px] text-indigo-400 uppercase tracking-wider font-semibold mb-2 flex items-center gap-1.5">
                      <UploadCloud size={13} className="text-indigo-400" />
                      Adding
                    </div>
                    <div className="space-y-1 font-mono text-indigo-200">
                      <div>+{datasetCounts.added.invoices} invoices</div>
                      <div>+{datasetCounts.added.settlements} settlements</div>
                      <div>+{datasetCounts.added.bank_transactions} bank transactions</div>
                      {(datasetCounts.added.refunds ?? 0) > 0 && (
                        <div>+{datasetCounts.added.refunds} refunds</div>
                      )}
                    </div>
                  </div>
                  <div className="p-3 bg-emerald-950/30 rounded-lg border border-emerald-500/20">
                    <div className="text-[10px] text-emerald-400 uppercase tracking-wider font-semibold mb-2 flex items-center gap-1.5">
                      <CheckCircle2 size={13} className="text-emerald-400" />
                      Result
                    </div>
                    <div className="space-y-1 font-mono text-emerald-200 font-semibold">
                      <div>{datasetCounts.result.invoices} invoices</div>
                      <div>{datasetCounts.result.settlements} settlements</div>
                      <div>{datasetCounts.result.bank_transactions} bank transactions</div>
                      {(datasetCounts.result.refunds ?? 0) > 0 && (
                        <div>{datasetCounts.result.refunds} refunds</div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              <div className="space-y-3">
                {validationSummaries.map((summary, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 bg-slate-950/40 border border-slate-700/60 rounded-xl space-y-2.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileText size={16} className="text-indigo-400" />
                        <span className="text-sm font-semibold text-slate-200">
                          {summary.filename}
                        </span>
                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                          {summary.file_type}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs">
                        <span className="text-emerald-400 font-semibold font-mono">
                          {summary.stats.valid_count} valid
                        </span>
                        {summary.stats.rejected_count > 0 && (
                          <span className="text-rose-400 font-semibold font-mono">
                            {summary.stats.rejected_count} rejected
                          </span>
                        )}
                        {summary.stats.warning_count > 0 && (
                          <span className="text-amber-400 font-semibold font-mono">
                            {summary.stats.warning_count} warnings
                          </span>
                        )}
                      </div>
                    </div>

                    {summary.warnings.length > 0 && (
                      <div className="text-[11px] text-amber-400/90 bg-amber-500/5 p-2 rounded border border-amber-500/20 space-y-1">
                        {summary.warnings.slice(0, 3).map((w, wIdx) => (
                          <div key={wIdx}>• {w}</div>
                        ))}
                      </div>
                    )}

                    {summary.errors.length > 0 && (
                      <div className="text-[11px] text-rose-400/90 bg-rose-500/5 p-2 rounded border border-rose-500/20 space-y-1">
                        {summary.errors.slice(0, 3).map((e, eIdx) => (
                          <div key={eIdx}>• {e}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between">
          <div>
            {step !== 'upload' && step !== 'validate' && (
              <button
                disabled={isLoading}
                onClick={() => {
                  setError(null);
                  setStep(step === 'map' ? 'inspect' : 'upload');
                }}
                className="px-3.5 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs font-medium flex items-center gap-1.5 transition"
              >
                <ArrowLeft size={14} /> Back
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              disabled={isLoading}
              className="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-slate-200 text-xs font-medium transition"
            >
              Cancel
            </button>

            {step === 'upload' && (
              <button
                disabled={selectedFiles.length === 0 || isLoading}
                onClick={handleStartProfiling}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-medium flex items-center gap-2 shadow-lg shadow-indigo-600/20 transition"
              >
                {isLoading ? (
                  <>
                    <RefreshCw size={14} className="animate-spin" />
                    Profiling CSVs...
                  </>
                ) : (
                  <>
                    Inspect & Profile <ArrowRight size={14} />
                  </>
                )}
              </button>
            )}

            {step === 'inspect' && (
              <button
                onClick={() => {
                  setError(null);
                  setStep('map');
                }}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-2 shadow-lg shadow-indigo-600/20 transition"
              >
                Confirm Schema Mapping <ArrowRight size={14} />
              </button>
            )}

            {step === 'map' && (
              <>
                <button
                  type="button"
                  onClick={() => handleAutoFixMappings()}
                  className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-indigo-500/40 text-indigo-200 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer"
                  title="Automatically assign matching columns for all missing required fields across all files"
                >
                  <Sparkles size={13} className="text-amber-300" />
                  Auto-Fix All Mappings
                </button>
                <button
                  disabled={isLoading}
                  onClick={handleConfirmAndValidate}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-medium flex items-center gap-2 shadow-lg shadow-indigo-600/20 transition"
                >
                  {isLoading ? (
                    <>
                      <RefreshCw size={14} className="animate-spin" />
                      Validating Rows...
                    </>
                  ) : (
                    <>
                      Validate & Ingest <Check size={14} />
                    </>
                  )}
                </button>
              </>
            )}

            {step === 'validate' && (
              <button
                onClick={handleFinalReconcile}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium flex items-center gap-2 shadow-lg shadow-emerald-600/20 transition"
              >
                Confirm & Update Active Dataset <Check size={14} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

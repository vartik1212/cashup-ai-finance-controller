// Format utilities for financial data display

export function formatCurrency(amount: number, currency = 'INR'): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  }).format(amount);
}

export function formatCurrencyFull(amount: number, currency = 'INR'): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(amount);
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDiff(diff: number): string {
  if (diff === 0) return '₹0';
  const sign = diff > 0 ? '+' : '';
  return sign + formatCurrency(diff);
}

export function formatPct(value: number): string {
  if (value == null || isNaN(value)) return '0.0%';
  const norm = value > 1 ? value / 100 : value;
  const clamped = Math.max(0, Math.min(1, norm));
  return `${(clamped * 100).toFixed(1)}%`;
}

export function formatMs(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('en-IN').format(n);
}

export function formatCompactCurrency(amount: number): string {
  if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(1)}Cr`;
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`;
  if (amount >= 1000) return `₹${(amount / 1000).toFixed(0)}K`;
  return `₹${amount.toFixed(0)}`;
}

export function scenarioLabel(scenario: string): string {
  const map: Record<string, string> = {
    exact_match: 'Exact Matches',
    fee_adjusted: 'Fee Matches',
    delayed_settlement: 'Delayed Settlements',
    partial_payment: 'Partial Payments',
    refund: 'Refunds',
    duplicate_payment: 'Duplicates',
    missing_settlement: 'Missing Settlements',
    incorrect_reference: 'Incorrect References',
    amount_mismatch: 'Amount Mismatches',
    ambiguous_match: 'Ambiguous Matches',
  };
  return map[scenario] ?? scenario;
}

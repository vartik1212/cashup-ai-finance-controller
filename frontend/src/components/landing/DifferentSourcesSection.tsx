import React, { useEffect, useRef, useState } from 'react';

interface TransactionRow {
  id: string;
  amount: string;
  date: string;
  subtext: string;
}

const INVOICE_DATA: TransactionRow[] = [
  { id: 'AR/26/4115', amount: '₹9,18,000', date: '05 Sep 2026', subtext: 'Razorpay Enterprise Tech' },
  { id: 'AR/26/4116', amount: '₹14,50,000', date: '05 Sep 2026', subtext: 'Global Cloud Services' },
  { id: 'AR/26/4117', amount: '₹3,25,000', date: '06 Sep 2026', subtext: 'Nexus Logistics Pvt' },
];

const SETTLEMENT_DATA: TransactionRow[] = [
  { id: 'SET-88421', amount: '₹9,18,000', date: '05 Sep 2026', subtext: 'Net Settled · Batch 942' },
  { id: 'SET-88422', amount: '₹14,21,000', date: '05 Sep 2026', subtext: 'MDR Deducted · ₹29k' },
  { id: 'SET-88423', amount: '₹3,25,000', date: '06 Sep 2026', subtext: 'Net Settled · Batch 943' },
];

const BANK_DATA: TransactionRow[] = [
  { id: 'UTR-629183', amount: '₹9,18,000', date: '05 Sep 2026', subtext: 'HDFC Corp Credit Ref' },
  { id: 'UTR-629184', amount: '₹14,21,000', date: '06 Sep 2026', subtext: 'ICICI Settlement Pool' },
  { id: 'UTR-629185', amount: '₹3,25,000', date: '06 Sep 2026', subtext: 'Axis Escrow Credit' },
];

export const DifferentSourcesSection: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const windowH = window.innerHeight;

      // Calculate progress from 0 (entering) to 1 (leaving)
      const start = windowH * 0.9;
      const end = -rect.height * 0.4;
      const current = start - rect.top;
      const total = start - end;
      const progress = Math.max(0, Math.min(1, current / total));
      setScrollProgress(progress);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Spatial convergence offsets based on scroll progress:
  // Starts separated (left: -40px, right: 40px, depths Z1/Z2), converges toward center as user scrolls
  const convergeFactor = Math.min(1, scrollProgress * 1.6);
  const leftX = (-36 * (1 - convergeFactor)).toFixed(1);
  const rightX = (36 * (1 - convergeFactor)).toFixed(1);
  const leftRotateY = (6 * (1 - convergeFactor)).toFixed(1);
  const rightRotateY = (-6 * (1 - convergeFactor)).toFixed(1);
  const leftZ = (-15 * (1 - convergeFactor)).toFixed(1);
  const centerZ = (12 * convergeFactor).toFixed(1);
  const rightZ = (-15 * (1 - convergeFactor)).toFixed(1);

  return (
    <section
      id="how-it-works"
      ref={containerRef}
      className="relative w-full py-24 sm:py-32 px-6 sm:px-8 border-t border-[#1F2E47]/40 overflow-hidden"
      style={{ perspective: '1100px' }}
    >
      <div className="max-w-5xl mx-auto">
        {/* Centered Section Copy */}
        <div className="text-center max-w-xl mx-auto mb-16 sm:mb-20">
          <div className="inline-block text-[11px] font-mono tracking-widest text-[#91A0B6] uppercase mb-3">
            PHASE 01 — MULTI-STREAM INGESTION
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight text-[#F4F7FB] leading-tight mb-4">
            Different sources.
            <br />
            <span className="text-[#91A0B6]">One financial truth.</span>
          </h2>
          <p className="text-sm sm:text-base text-[#91A0B6] font-normal leading-relaxed">
            CashUP connects evidence across the financial stack.
          </p>
        </div>

        {/* Three Thin Spatial Ledger Strips */}
        <div
          className="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-6 relative transition-transform duration-200 ease-out"
          style={{ transformStyle: 'preserve-3d' }}
        >
          {/* Stream 1: INVOICES (Left ledger strip) */}
          <div
            className="rounded-xl bg-[#101A2B]/80 border border-[#1F2E47] p-4.5 backdrop-blur-sm shadow-[0_12px_32px_rgba(5,11,20,0.4)] transition-all duration-300"
            style={{
              transform: `translateX(${leftX}px) translateZ(${leftZ}px) rotateY(${leftRotateY}deg)`,
            }}
          >
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1F2E47]/70">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#91A0B6]" />
                <span className="text-xs font-mono font-semibold tracking-wider text-[#F4F7FB] uppercase">
                  INVOICES
                </span>
              </div>
              <span className="text-[10px] font-mono text-[#91A0B6]">ERP Ledger</span>
            </div>

            <div className="space-y-2.5">
              {INVOICE_DATA.map((row) => (
                <div
                  key={row.id}
                  className="p-2.5 rounded-lg bg-[#07111F]/70 border border-[#1A263D] hover:border-[#2A3B59] transition-colors"
                >
                  <div className="flex items-center justify-between text-xs font-mono mb-1">
                    <span className="font-semibold text-[#F4F7FB]">{row.id}</span>
                    <span className="text-[#F4F7FB] font-medium">{row.amount}</span>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-[#91A0B6] font-mono">
                    <span className="truncate pr-2">{row.subtext}</span>
                    <span className="flex-shrink-0">{row.date}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-3 pt-2.5 border-t border-[#1F2E47]/50 flex items-center justify-between text-[10px] font-mono text-[#91A0B6]">
              <span>Feed: NetSuite / SAP</span>
              <span className="text-[#22D3EE]">Indexed</span>
            </div>
          </div>

          {/* Stream 2: SETTLEMENTS (Center ledger strip) */}
          <div
            className="rounded-xl bg-[#101A2B] border border-[#273854] p-4.5 backdrop-blur-sm shadow-[0_16px_40px_rgba(5,11,20,0.6)] relative z-10 transition-all duration-300"
            style={{
              transform: `translateZ(${centerZ}px)`,
            }}
          >
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1F2E47]/70">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#22D3EE]" />
                <span className="text-xs font-mono font-semibold tracking-wider text-[#F4F7FB] uppercase">
                  SETTLEMENTS
                </span>
              </div>
              <span className="text-[10px] font-mono text-[#91A0B6]">Gateway Feed</span>
            </div>

            <div className="space-y-2.5">
              {SETTLEMENT_DATA.map((row) => (
                <div
                  key={row.id}
                  className="p-2.5 rounded-lg bg-[#07111F]/80 border border-[#1F2E47] hover:border-[#2E4366] transition-colors"
                >
                  <div className="flex items-center justify-between text-xs font-mono mb-1">
                    <span className="font-semibold text-[#22D3EE]">{row.id}</span>
                    <span className="text-[#F4F7FB] font-medium">{row.amount}</span>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-[#91A0B6] font-mono">
                    <span className="truncate pr-2">{row.subtext}</span>
                    <span className="flex-shrink-0">{row.date}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-3 pt-2.5 border-t border-[#1F2E47]/50 flex items-center justify-between text-[10px] font-mono text-[#91A0B6]">
              <span>Feed: Razorpay / Stripe</span>
              <span className="text-[#22D3EE]">Batched</span>
            </div>
          </div>

          {/* Stream 3: BANK (Right ledger strip) */}
          <div
            className="rounded-xl bg-[#101A2B]/80 border border-[#1F2E47] p-4.5 backdrop-blur-sm shadow-[0_12px_32px_rgba(5,11,20,0.4)] transition-all duration-300"
            style={{
              transform: `translateX(${rightX}px) translateZ(${rightZ}px) rotateY(${rightRotateY}deg)`,
            }}
          >
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1F2E47]/70">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#91A0B6]" />
                <span className="text-xs font-mono font-semibold tracking-wider text-[#F4F7FB] uppercase">
                  BANK
                </span>
              </div>
              <span className="text-[10px] font-mono text-[#91A0B6]">Direct Statements</span>
            </div>

            <div className="space-y-2.5">
              {BANK_DATA.map((row) => (
                <div
                  key={row.id}
                  className="p-2.5 rounded-lg bg-[#07111F]/70 border border-[#1A263D] hover:border-[#2A3B59] transition-colors"
                >
                  <div className="flex items-center justify-between text-xs font-mono mb-1">
                    <span className="font-semibold text-[#F4F7FB]">{row.id}</span>
                    <span className="text-[#F4F7FB] font-medium">{row.amount}</span>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-[#91A0B6] font-mono">
                    <span className="truncate pr-2">{row.subtext}</span>
                    <span className="flex-shrink-0">{row.date}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-3 pt-2.5 border-t border-[#1F2E47]/50 flex items-center justify-between text-[10px] font-mono text-[#91A0B6]">
              <span>Feed: MT940 / CAMT.053</span>
              <span className="text-[#22D3EE]">Cleared</span>
            </div>
          </div>
        </div>

        {/* Three continuous connector feeder stems leading directly into the reconciliation engine */}
        <div className="mt-14 flex flex-col items-center">
          <div className="flex items-center justify-center gap-3 text-xs font-mono text-[#91A0B6]/70 mb-4">
            <span className="h-px w-12 bg-[#1F2E47]" />
            <span>Streams converge into verification core ↓</span>
            <span className="h-px w-12 bg-[#1F2E47]" />
          </div>

          <div className="grid grid-cols-3 w-full max-w-2xl h-10 px-12">
            <div className="flex justify-center">
              <div className="w-px h-full bg-gradient-to-b from-[#1F2E47] to-[#22D3EE]/60" />
            </div>
            <div className="flex justify-center">
              <div className="w-px h-full bg-gradient-to-b from-[#22D3EE]/80 to-[#22D3EE]" />
            </div>
            <div className="flex justify-center">
              <div className="w-px h-full bg-gradient-to-b from-[#1F2E47] to-[#22D3EE]/60" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

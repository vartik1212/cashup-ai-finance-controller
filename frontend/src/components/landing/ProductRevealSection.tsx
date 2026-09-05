import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronUp, Layers, Check, AlertTriangle, ShieldCheck, Database, GitMerge } from 'lucide-react';

export const ProductRevealSection: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [revealProgress, setRevealProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const windowH = window.innerHeight;

      // Progress from 0 (approaching) to 1 (fully centered)
      const start = windowH * 0.9;
      const end = windowH * 0.1;
      const current = start - rect.top;
      const total = start - end;
      const progress = Math.max(0, Math.min(1, current / total));
      setRevealProgress(progress);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Smooth straightens from perspective 10deg, scale 0.93 to 0deg, scale 1.0
  const tiltDeg = (10 * (1 - revealProgress)).toFixed(2);
  const scaleVal = (0.93 + 0.07 * revealProgress).toFixed(3);
  const translateYVal = (35 * (1 - revealProgress)).toFixed(1);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const scrollToArchitecture = (e: React.MouseEvent) => {
    e.preventDefault();
    const el = document.getElementById('architecture');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section
      ref={containerRef}
      className="relative w-full pt-16 sm:pt-20 pb-8 sm:pb-10 px-6 sm:px-8 border-t border-[#1F2E47]/60 bg-[#07111F] overflow-hidden"
    >
      <div className="max-w-6xl mx-auto">
        
        {/* Headings & Emergence Copy */}
        <div className="text-center max-w-2xl mx-auto mb-16 sm:mb-20">
          <div className="inline-block text-[11px] font-mono tracking-widest text-[#91A0B6] uppercase mb-3">
            THE PRODUCTION PLATFORM
          </div>
          <h2 className="text-3xl sm:text-5xl font-semibold tracking-tight text-[#F4F7FB] leading-[1.12] mb-4">
            From fragmented transactions
            <br />
            <span className="text-[#91A0B6]">to verified financial truth.</span>
          </h2>
          <p className="text-sm sm:text-base text-[#91A0B6] font-normal">
            Reconcile. Verify. Investigate. Report.
          </p>
        </div>

        {/* Emerging Dashboard Preview with Scroll-Straightening Perspective */}
        <div
          className="w-full max-w-5xl mx-auto mb-20 transition-transform duration-200 ease-out"
          style={{
            perspective: '1200px',
          }}
        >
          <div
            className="rounded-2xl bg-[#0A1220] border border-[#1F2E47] shadow-[0_25px_80px_rgba(0,0,0,0.7)] overflow-hidden transition-all duration-300"
            style={{
              transform: `rotateX(${tiltDeg}deg) scale(${scaleVal}) translateY(${translateYVal}px)`,
              transformStyle: 'preserve-3d',
            }}
          >
            {/* Window chrome header */}
            <div className="px-5 py-3.5 bg-[#101A2B] border-b border-[#1F2E47] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#EF5B67]/70" />
                  <span className="w-2.5 h-2.5 rounded-full bg-[#F4B740]/70" />
                  <span className="w-2.5 h-2.5 rounded-full bg-[#2DD4A7]/70" />
                </div>
                <span className="text-xs font-mono font-medium text-[#91A0B6] ml-2">
                  CashUP Controller Console — Production Workspace
                </span>
              </div>

              <div className="flex items-center gap-3 text-xs font-mono">
                <span className="px-2 py-0.5 rounded bg-[#07111F] text-[#22D3EE] border border-[#22D3EE]/30">
                  RUN-8492 · COMPLETED
                </span>
                <span className="hidden sm:inline text-[#2DD4A7] flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#2DD4A7]" />
                  99.8% Precision
                </span>
              </div>
            </div>

            {/* Dashboard Inner Body Preview */}
            <div className="p-6 sm:p-8 bg-[#07111F]/95 space-y-6">
              
              {/* Summary Metric Ribbon */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl bg-[#101A2B] border border-[#1F2E47]">
                  <div className="text-[11px] font-mono text-[#91A0B6]">TOTAL INGESTION</div>
                  <div className="text-xl font-mono font-bold text-[#F4F7FB] mt-1">₹2,56,40,000</div>
                  <div className="text-[10px] text-[#91A0B6] mt-1">72 Ledger records</div>
                </div>

                <div className="p-4 rounded-xl bg-[#2DD4A7]/10 border border-[#2DD4A7]/30">
                  <div className="text-[11px] font-mono text-[#2DD4A7]">AUTO-VERIFIED</div>
                  <div className="text-xl font-mono font-bold text-[#2DD4A7] mt-1">45 Records</div>
                  <div className="text-[10px] text-[#2DD4A7]/80 mt-1">Cleared straight to GL</div>
                </div>

                <div className="p-4 rounded-xl bg-[#F4B740]/10 border border-[#F4B740]/30">
                  <div className="text-[11px] font-mono text-[#F4B740]">FEE & TIMING REVIEW</div>
                  <div className="text-xl font-mono font-bold text-[#F4B740] mt-1">21 Exceptions</div>
                  <div className="text-[10px] text-[#F4B740]/80 mt-1">MDR variances isolated</div>
                </div>

                <div className="p-4 rounded-xl bg-[#EF5B67]/10 border border-[#EF5B67]/30">
                  <div className="text-[11px] font-mono text-[#EF5B67]">UNRESOLVED DISCREPANCY</div>
                  <div className="text-xl font-mono font-bold text-[#EF5B67] mt-1">6 Records</div>
                  <div className="text-[10px] text-[#EF5B67]/80 mt-1">Missing gateway trace</div>
                </div>
              </div>

              {/* Sample High-Precision Ledger Rows */}
              <div className="rounded-xl border border-[#1F2E47] bg-[#0A1220] overflow-hidden">
                <div className="px-4 py-2.5 bg-[#101A2B] border-b border-[#1F2E47] grid grid-cols-12 text-[11px] font-mono text-[#91A0B6] font-semibold">
                  <div className="col-span-3">INVOICE ID</div>
                  <div className="col-span-3">SETTLEMENT / UTR</div>
                  <div className="col-span-2 text-right">AMOUNT</div>
                  <div className="col-span-2 text-center">STATUS</div>
                  <div className="col-span-2 text-right">CONFIDENCE</div>
                </div>

                <div className="divide-y divide-[#1F2E47]/50 text-xs font-mono">
                  {/* Row 1: Exact Match */}
                  <div className="px-4 py-3 grid grid-cols-12 items-center text-[#F4F7FB] hover:bg-[#101A2B]/40">
                    <div className="col-span-3 font-semibold">AR/26/4115</div>
                    <div className="col-span-3 text-[#91A0B6]">SET-88421 / UTR-629183</div>
                    <div className="col-span-2 text-right font-medium">₹9,18,000</div>
                    <div className="col-span-2 text-center">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#2DD4A7]/15 text-[#2DD4A7] border border-[#2DD4A7]/30">
                        Exact Match
                      </span>
                    </div>
                    <div className="col-span-2 text-right text-[#2DD4A7] font-semibold">100%</div>
                  </div>

                  {/* Row 2: Fee Adjusted */}
                  <div className="px-4 py-3 grid grid-cols-12 items-center text-[#F4F7FB] hover:bg-[#101A2B]/40">
                    <div className="col-span-3 font-semibold">AR/26/4116</div>
                    <div className="col-span-3 text-[#91A0B6]">SET-88422 / UTR-629184</div>
                    <div className="col-span-2 text-right font-medium">₹14,50,000</div>
                    <div className="col-span-2 text-center">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#22D3EE]/15 text-[#22D3EE] border border-[#22D3EE]/30">
                        Fee Adjusted
                      </span>
                    </div>
                    <div className="col-span-2 text-right text-[#22D3EE] font-semibold">95%</div>
                  </div>

                  {/* Row 3: Review Required Exception */}
                  <div className="px-4 py-3 grid grid-cols-12 items-center text-[#F4F7FB] hover:bg-[#101A2B]/40">
                    <div className="col-span-3 font-semibold">AR/26/4118</div>
                    <div className="col-span-3 text-[#91A0B6]">SET-88424 [Pending Bank]</div>
                    <div className="col-span-2 text-right font-medium">₹5,80,000</div>
                    <div className="col-span-2 text-center">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#F4B740]/15 text-[#F4B740] border border-[#F4B740]/30">
                        Review Required
                      </span>
                    </div>
                    <div className="col-span-2 text-right text-[#F4B740] font-semibold">70%</div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>

        {/* Final Calls to Action */}
        <div className="text-center flex flex-col sm:flex-row items-center justify-center gap-4 mb-12 sm:mb-14">
          <Link
            to="/app"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-7 py-3.5 rounded-xl bg-[#6C5CE7] hover:bg-[#5b4bc4] text-sm font-semibold text-[#F4F7FB] shadow-[0_6px_28px_rgba(108,92,231,0.35)] hover:shadow-[0_8px_36px_rgba(108,92,231,0.5)] transition-all duration-200 cursor-pointer active:scale-[0.98]"
          >
            <span>Launch CashUP</span>
            <ArrowRight size={15} />
          </Link>

          <a
            href="#architecture"
            onClick={scrollToArchitecture}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-[#101A2B] hover:bg-[#16233B] border border-[#1F2E47] hover:border-[#2D4163] text-sm font-medium text-[#91A0B6] hover:text-[#F4F7FB] transition-all duration-200 cursor-pointer"
          >
            <span>View Architecture</span>
          </a>
        </div>

        {/* Minimal, Perfectly Aligned Footer */}
        <footer className="pt-6 pb-2 border-t border-[#1F2E47]/60 flex flex-col md:flex-row items-center justify-between gap-4 text-xs font-mono text-[#91A0B6]">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#2DD4A7] shadow-[0_0_6px_#2DD4A7]" />
            <span className="font-semibold text-[#F4F7FB]">CashUP</span>
            <span className="text-[#1F2E47]">|</span>
            <span>Deterministic Core v2.4</span>
          </div>

          <div className="text-center text-[11px] text-[#91A0B6]/80">
            Autonomous, auditable multi-source financial reconciliation.
          </div>

          <div className="flex items-center gap-4">
            <span className="text-[11px] text-[#91A0B6]/60">© 2026 CashUP</span>
            <button
              onClick={scrollToTop}
              className="flex items-center gap-1 px-2.5 py-1 rounded bg-[#101A2B] hover:bg-[#16233B] border border-[#1F2E47] text-[#91A0B6] hover:text-[#F4F7FB] transition-colors cursor-pointer text-[11px]"
              title="Return to top"
            >
              <span>Top</span>
              <ChevronUp size={12} />
            </button>
          </div>
        </footer>

      </div>
    </section>
  );
};

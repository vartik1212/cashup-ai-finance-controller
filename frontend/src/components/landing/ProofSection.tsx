import React from 'react';

export const ProofSection: React.FC = () => {
  return (
    <section
      id="proof"
      className="relative w-full py-16 sm:py-20 px-6 sm:px-8 border-t border-[#1F2E47]/50 bg-[#050B14] overflow-hidden"
    >
      <div className="max-w-5xl mx-auto">
        {/* Eyebrow */}
        <div className="text-center mb-16 sm:mb-20">
          <div className="inline-block text-[11px] font-mono tracking-widest text-[#91A0B6] uppercase mb-3">
            PROOF, NOT PROMISES.
          </div>
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight text-[#F4F7FB]">
            Tested against production ledger variances.
          </h2>
        </div>

        {/* Large Numbers with generous whitespace and balanced responsive grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 2xl:grid-cols-4 gap-4 sm:gap-6 lg:gap-8 mb-16 sm:mb-20 text-center">
          {/* Metric 1 */}
          <div className="flex flex-col justify-center min-h-[150px] p-6 rounded-2xl bg-[#07111F]/70 border border-[#1F2E47]/80 shadow-[0_8px_24px_rgba(5,11,20,0.4)]">
            <div className="text-3xl sm:text-4xl lg:text-5xl font-bold font-mono tracking-tight text-[#F4F7FB] mb-2">
              72
            </div>
            <div className="text-xs sm:text-sm font-medium text-[#91A0B6]">
              Records processed
            </div>
          </div>

          {/* Metric 2 */}
          <div className="flex flex-col justify-center min-h-[150px] p-6 rounded-2xl bg-[#07111F]/70 border border-[#1F2E47]/80 shadow-[0_8px_24px_rgba(5,11,20,0.4)]">
            <div className="text-3xl sm:text-4xl lg:text-5xl font-bold font-mono tracking-tight text-[#F4F7FB] mb-2">
              ₹2.56Cr
            </div>
            <div className="text-xs sm:text-sm font-medium text-[#91A0B6]">
              Reconciled value
            </div>
          </div>

          {/* Metric 3 */}
          <div className="flex flex-col justify-center min-h-[150px] p-6 rounded-2xl bg-[#07111F]/70 border border-[#1F2E47]/80 shadow-[0_8px_24px_rgba(5,11,20,0.4)]">
            <div className="text-3xl sm:text-4xl lg:text-5xl font-bold font-mono tracking-tight text-[#F4B740] mb-2">
              27
            </div>
            <div className="text-xs sm:text-sm font-medium text-[#91A0B6]">
              Exceptions surfaced
            </div>
          </div>

          {/* Metric 4 (Honest evaluation, no fake percentage) */}
          <div className="flex flex-col justify-center min-h-[150px] p-6 rounded-2xl bg-[#07111F]/70 border border-[#1F2E47]/80 shadow-[0_8px_24px_rgba(5,11,20,0.4)]">
            <div className="text-3xl sm:text-4xl lg:text-5xl font-bold font-mono tracking-tight text-[#2DD4A7] mb-2">
              Measured
            </div>
            <div className="text-xs sm:text-sm font-medium text-[#91A0B6]">
              Accuracy benchmark
            </div>
          </div>
        </div>

        {/* Supporting Tri-statement */}
        <div className="text-center max-w-2xl mx-auto space-y-4">
          <div className="text-lg sm:text-xl font-medium text-[#F4F7FB] tracking-tight">
            50+ records. Measured accuracy. Honest exceptions.
          </div>
          <p className="text-sm text-[#91A0B6] leading-relaxed">
            Built around the core principle that uncertain financial records should be surfaced, not silently cleared.
          </p>
        </div>
      </div>
    </section>
  );
};
